import secrets
from urllib.parse import quote

import questionary

from fastapi_wizard.config import WizardConfig


class WizardCancelled(Exception):
    pass


def _ask(prompt):
    answer = prompt.ask()
    if answer is None:
        raise WizardCancelled
    return answer


def collect_config(project_name: str) -> tuple[WizardConfig, bool, bool]:
    db_type = _ask(
        questionary.select(
            "¿Qué base de datos utilizarás?",
            choices=["PostgreSQL", "MySQL", "MariaDB", "SQLite"],
        )
    )

    db_user = ""
    db_password = ""
    db_name = ""
    db_port = ""
    if db_type == "SQLite":
        database_url = "sqlite:///./app.db"
    else:
        db_user = _ask(questionary.text("Usuario de la BD:", default="admin"))
        db_password = _ask(questionary.password("Contraseña de la BD:"))
        db_port = _ask(
            questionary.text(
                "Puerto de la BD:",
                default="5432" if db_type == "PostgreSQL" else "3306",
            )
        )
        db_name = _ask(
            questionary.text(
                "Nombre de la base de datos:",
                default=f"{project_name}_db",
            )
        )

        driver = {
            "PostgreSQL": "postgresql+psycopg",
            "MySQL": "mysql+pymysql",
            "MariaDB": "mysql+pymysql",
        }[db_type]
        database_url = (
            f"{driver}://{quote(db_user, safe='')}:{quote(db_password, safe='')}"
            f"@localhost:{db_port}/{quote(db_name, safe='')}"
        )

    hashing_algo = _ask(
        questionary.select(
            "Algoritmo de hasheo de contraseñas:",
            choices=["bcrypt", "argon2"],
        )
    )
    token_algo = _ask(
        questionary.select(
            "Algoritmo para el token JWT (esta plantilla usa clave compartida):",
            choices=["HS256"],
        )
    )
    secret_key = _ask(
        questionary.text(
            "Clave secreta JWT (dejar vacío para generar una aleatoria):"
        )
    ) or secrets.token_urlsafe(32)

    use_alembic = _ask(
        questionary.confirm(
            "¿Deseas instalar y configurar Alembic para migraciones?"
        )
    )
    create_user_structure = _ask(
        questionary.confirm(
            "¿Deseas generar el modelo, schema y endpoint de registro de Usuario?"
        )
    )

    minio_user = _ask(questionary.text("Usuario Root de MinIO:", default="admin"))
    minio_password = _ask(questionary.password("Contraseña Root de MinIO:"))

    config = WizardConfig(
        project_name=project_name,
        db_type=db_type,
        database_url=database_url,
        secret_key=secret_key,
        hashing_algo=hashing_algo,
        token_algo=token_algo,
        minio_user=minio_user,
        minio_password=minio_password,
        db_user=db_user,
        db_password=db_password,
        db_name=db_name,
        db_port=db_port,
        use_alembic=use_alembic,
    )
    return config, use_alembic, create_user_structure
