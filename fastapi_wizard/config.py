from dataclasses import dataclass


@dataclass(frozen=True)
class WizardConfig:
    project_name: str
    db_type: str
    database_url: str
    secret_key: str
    hashing_algo: str
    token_algo: str
    minio_user: str
    minio_password: str
    use_alembic: bool = False
    db_user: str = ""
    db_password: str = ""
    db_name: str = ""
    db_port: str = ""
