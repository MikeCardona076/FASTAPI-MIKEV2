import json
from pathlib import Path

from fastapi_wizard.config import WizardConfig


DB_IMAGES = {
    "PostgreSQL": ("postgres:15-alpine", "postgresql/data", "5432"),
    "MySQL": ("mysql:8.0", "mysql/data", "3306"),
    "MariaDB": ("mariadb:10.11", "mysql/data", "3306"),
}

PROJECT_TEMPLATES = {
    "core/config.py": '''from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "{project_name}"
    DATABASE_URL: str
    SECRET_KEY: str
    HASHING_ALGORITHM: str = "{hashing_algo}"
    TOKEN_ALGORITHM: str = "{token_algo}"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    USE_ALEMBIC: bool = {use_alembic}
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
''',
    "core/security.py": '''from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from core.config import settings


password_context = CryptContext(
    schemes=[settings.HASHING_ALGORITHM],
    deprecated="auto",
)


def get_password_hash(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_context.verify(password, hashed_password)


def create_access_token(data: dict, expires_delta=None) -> str:
    payload = data.copy()
    expires_at = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload["exp"] = expires_at
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.TOKEN_ALGORITHM,
    )
''',
    "db/database.py": '''from collections.abc import Generator

from sqlmodel import Session, create_engine

from core.config import settings

connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
''',
    "models/__init__.py": '''from models.user_model import Usuario

__all__ = ["Usuario"]
''',
    "models/user_model.py": '''from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Usuario(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=3, max_length=50)
    email: str = Field(index=True, unique=True, max_length=320)
    hashed_password: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
''',
    "schemas/__init__.py": "",
    "schemas/user_schema.py": '''from datetime import datetime

from pydantic import EmailStr, Field
from sqlmodel import SQLModel


class UserCreate(SQLModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length={password_max_length})


class UserResponse(SQLModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(SQLModel):
    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = None
    password: str | None = Field(
        default=None,
        min_length=8,
        max_length={password_max_length},
    )
    is_active: bool | None = None
''',
    "schemas/token_schema.py": '''from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
''',
    "api/__init__.py": "",
    "api/v1/__init__.py": "",
    "api/v1/dependencies.py": '''from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session, select

from core.config import settings
from db.database import get_session
from models.user_model import Usuario

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/users/token",
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.TOKEN_ALGORITHM],
        )
        username = payload.get("sub")
        if not isinstance(username, str) or not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception from None

    user = session.exec(
        select(Usuario).where(Usuario.username == username)
    ).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo.",
        )
    return user
''',
    "api/v1/user_api.py": '''from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from datetime import timedelta
from typing import Annotated

from api.v1.dependencies import get_current_user
from core.config import settings
from core.security import create_access_token, get_password_hash, verify_password
from db.database import get_session
from models.user_model import Usuario
from schemas.token_schema import Token
from schemas.user_schema import UserCreate, UserResponse, UserUpdate

router = APIRouter()


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session),
) -> Token:
    user = session.exec(
        select(Usuario).where(Usuario.username == form_data.username)
    ).first()
    if user is None or not verify_password(
        form_data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo.",
        )

    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        ),
    )
    return Token(access_token=access_token)


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user_data: UserCreate,
    session: Session = Depends(get_session),
) -> Usuario:
    existing_user = session.exec(
        select(Usuario).where(
            (Usuario.username == user_data.username)
            | (Usuario.email == user_data.email)
        )
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario o correo ya está registrado.",
        )

    user = Usuario(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario o correo ya está registrado.",
        ) from None
    session.refresh(user)
    return user


@router.get("/", response_model=list[UserResponse])
def get_users(
    session: Session = Depends(get_session),
    _current_user: Usuario = Depends(get_current_user),
) -> list[Usuario]:
    return list(session.exec(select(Usuario)).all())


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    session: Session = Depends(get_session),
    _current_user: Usuario = Depends(get_current_user),
) -> Usuario:
    user = session.get(Usuario, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    session: Session = Depends(get_session),
    _current_user: Usuario = Depends(get_current_user),
) -> Usuario:
    user = session.get(Usuario, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    update_data = user_update.model_dump(exclude_unset=True)
    if any(value is None for value in update_data.values()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Los campos enviados no pueden ser null.",
        )

    if "username" in update_data or "email" in update_data:
        duplicate = session.exec(
            select(Usuario).where(
                Usuario.id != user_id,
                (Usuario.username == update_data.get("username", user.username))
                | (Usuario.email == update_data.get("email", user.email)),
            )
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El usuario o correo ya está registrado.",
            )

    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(
            update_data.pop("password")
        )
    for field, value in update_data.items():
        setattr(user, field, value)

    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario o correo ya está registrado.",
        ) from None
    session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    session: Session = Depends(get_session),
    _current_user: Usuario = Depends(get_current_user),
) -> None:
    user = session.get(Usuario, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )
    session.delete(user)
    session.commit()
''',
    "main.py": '''from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel
from fastapi.middleware.cors import CORSMiddleware

from models import user_model
from api.v1.user_api import router as users_router
from core.config import settings
from db.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.USE_ALEMBIC:
        SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
''',
    "alembic/env.py": '''from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from core.config import settings
from models import user_model

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_URL.replace("%", "%%"),
)
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
''',
    "alembic/script.py.mako": '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
''',
    "alembic.ini": '''[alembic]
script_location = %(here)s/alembic
prepend_sys_path = .
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
''',
}


def _yaml_string(value: str) -> str:
    return json.dumps(value)


def render_docker_compose(config: WizardConfig) -> str:
    project = config.project_name
    services: list[str] = []
    volumes: list[str] = []

    if config.db_type in DB_IMAGES:
        image, volume_path, default_port = DB_IMAGES[config.db_type]
        db_port = config.db_port or default_port
        if config.db_type == "PostgreSQL":
            database_environment = (
                f"      POSTGRES_USER: {_yaml_string(config.db_user)}\n"
                f"      POSTGRES_PASSWORD: {_yaml_string(config.db_password)}\n"
                f"      POSTGRES_DB: {_yaml_string(config.db_name)}"
            )
        else:
            database_environment = (
                f"      MYSQL_ROOT_PASSWORD: {_yaml_string(config.db_password)}\n"
                f"      MYSQL_USER: {_yaml_string(config.db_user)}\n"
                f"      MYSQL_PASSWORD: {_yaml_string(config.db_password)}\n"
                f"      MYSQL_DATABASE: {_yaml_string(config.db_name)}"
            )
        services.append(
            f"  db:\n"
            f"    image: {image}\n"
            f"    container_name: {project}_db\n"
            f"    environment:\n{database_environment}\n"
            f"    ports:\n"
            f'      - "{db_port}:{default_port}"\n'
            f"    volumes:\n"
            f"      - {project}_db_data:/var/lib/{volume_path}\n"
            f"    restart: unless-stopped"
        )
        volumes.append(f"  {project}_db_data:")

    services.extend(
        [
            f"  redis:\n"
            f"    image: redis:7-alpine\n"
            f"    container_name: {project}_redis\n"
            f'    ports:\n      - "6379:6379"\n'
            f"    volumes:\n"
            f"      - {project}_redis_data:/data\n"
            f"    restart: unless-stopped",
            f"  minio:\n"
            f"    image: chainguard/minio:latest\n"
            f"    container_name: {project}_minio\n"
            f'    user: "65532:65532"\n'
            f'    ports:\n      - "9000:9000"\n      - "9001:9001"\n'
            f"    environment:\n"
            f"      MINIO_ROOT_USER: {_yaml_string(config.minio_user)}\n"
            f"      MINIO_ROOT_PASSWORD: {_yaml_string(config.minio_password)}\n"
            f"    volumes:\n"
            f"      - ./minio_data:/data\n"
            f'    command: server /data --console-address ":9001"\n'
            f"    restart: unless-stopped",
        ]
    )
    volumes.append(f"  {project}_redis_data:")

    return (
        "services:\n"
        + "\n\n".join(services)
        + "\n\nvolumes:\n"
        + "\n".join(volumes)
        + "\n"
    )


def render_env(config: WizardConfig) -> str:
    return (
        "# Configuración generada automáticamente por wizard.py\n"
        f"PROJECT_NAME={config.project_name}\n\n"
        "# Base de Datos\n"
        f"DATABASE_URL={json.dumps(config.database_url)}\n\n"
        "# Seguridad\n"
        f"SECRET_KEY={json.dumps(config.secret_key)}\n"
        f"HASHING_ALGORITHM={config.hashing_algo}\n"
        f"TOKEN_ALGORITHM={config.token_algo}\n"
        "ACCESS_TOKEN_EXPIRE_MINUTES=30\n\n"
        "# CORS (orígenes locales de desarrollo)\n"
        'CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]\n\n'
        f"USE_ALEMBIC={'true' if config.use_alembic else 'false'}\n\n"
        "# Redis\n"
        "REDIS_URL=redis://localhost:6379\n\n"
        "# MinIO\n"
        "MINIO_ENDPOINT=localhost:9000\n"
        f"MINIO_ROOT_USER={json.dumps(config.minio_user)}\n"
        f"MINIO_ROOT_PASSWORD={json.dumps(config.minio_password)}\n"
        "MINIO_BUCKET_NAME=uploads\n"
    )


def render_project_requirements(config: WizardConfig) -> str:
    requirements = [
        "fastapi[standard]>=0.115,<1",
        "sqlmodel>=0.0.22,<1",
        "pydantic-settings>=2.6,<3",
        "email-validator>=2.2,<3",
        "passlib[argon2,bcrypt]>=1.7.4,<2",
        "python-jose[cryptography]>=3.3,<4",
        "python-multipart>=0.0.18,<1",
        "redis>=5,<7",
        "minio>=7.2,<8",
    ]
    if config.db_type == "PostgreSQL":
        requirements.append("psycopg[binary]>=3.2,<4")
    elif config.db_type in ("MySQL", "MariaDB"):
        requirements.append("PyMySQL>=1.1,<2")
    if config.use_alembic:
        requirements.append("alembic>=1.14,<2")
    return "\n".join(requirements) + "\n"


def write_project_files(
    project_root: Path,
    config: WizardConfig,
    create_user_structure: bool,
) -> None:
    (project_root / "docker-compose.yml").write_text(
        render_docker_compose(config),
        encoding="utf-8",
    )
    (project_root / ".env").write_text(render_env(config), encoding="utf-8")
    (project_root / ".gitignore").write_text(
        ".venv/\n__pycache__/\n*.py[cod]\n.env\nminio_data/\n",
        encoding="utf-8",
    )
    (project_root / "minio_data").mkdir(exist_ok=True)
    (project_root / "requirements.txt").write_text(
        render_project_requirements(config),
        encoding="utf-8",
    )

    if config.use_alembic:
        (project_root / "alembic" / "versions").mkdir(parents=True, exist_ok=True)

    if create_user_structure or config.use_alembic:
        template_values = {
            "project_name": config.project_name,
            "hashing_algo": config.hashing_algo,
            "token_algo": config.token_algo,
            "use_alembic": "True" if config.use_alembic else "False",
            "password_max_length": "72" if config.hashing_algo == "bcrypt" else "128",
        }
        for relative_path, template in PROJECT_TEMPLATES.items():
            target = project_root.joinpath(*relative_path.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            rendered = template
            for key, value in template_values.items():
                rendered = rendered.replace("{" + key + "}", value)
            target.write_text(
                rendered,
                encoding="utf-8",
            )

        if config.use_alembic:
            (project_root / "alembic" / "versions" / ".gitkeep").touch()
