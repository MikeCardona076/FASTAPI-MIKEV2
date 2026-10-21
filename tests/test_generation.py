import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi_wizard.config import WizardConfig
from fastapi_wizard.generation import (
    PROJECT_TEMPLATES,
    render_docker_compose,
    render_env,
    write_project_files,
)
from wizard import _create_project_directory, _get_project_name


def make_config(db_type: str = "SQLite", **overrides: str) -> WizardConfig:
    values = {
        "project_name": "sample_api",
        "db_type": db_type,
        "database_url": "sqlite:///./app.db",
        "secret_key": "secret",
        "hashing_algo": "bcrypt",
        "token_algo": "HS256",
        "minio_user": "admin",
        "minio_password": "secret",
    }
    values.update(overrides)
    return WizardConfig(**values)


class GenerationTests(unittest.TestCase):
    def test_sqlite_compose_omits_database_service(self) -> None:
        compose = render_docker_compose(make_config())

        self.assertNotIn("\n  db:\n", compose)
        self.assertIn("  redis:", compose)
        self.assertIn("  minio:", compose)
        self.assertNotIn("sample_api_db_data:", compose)

    def test_database_credentials_are_quoted_in_compose(self) -> None:
        compose = render_docker_compose(
            make_config(
                db_type="PostgreSQL",
                db_user="user",
                db_password="pass:#word",
                db_name="sample",
                db_port="5433",
            )
        )

        self.assertIn('POSTGRES_PASSWORD: "pass:#word"', compose)
        self.assertIn('"5433:5432"', compose)

    def test_env_values_are_quoted(self) -> None:
        env_file = render_env(make_config(secret_key="value # with spaces"))

        self.assertIn('SECRET_KEY="value # with spaces"', env_file)

    def test_configuration_file_does_not_replace_virtual_environment_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            write_project_files(root, make_config(), create_user_structure=False)

            self.assertTrue((root / ".env").is_file())
            self.assertFalse((root / ".venv").exists())
            self.assertTrue((root / "docker-compose.yml").is_file())
            self.assertTrue((root / ".gitignore").is_file())
            self.assertFalse(
                any("\\" in path.name for path in root.rglob("*")),
                "Generated paths must use native directories, not backslash filenames.",
            )

    def test_user_scaffold_includes_model_registration_and_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            write_project_files(root, make_config(), create_user_structure=True)

            model = (root / "models" / "user_model.py").read_text(encoding="utf-8")
            endpoint = (root / "api" / "v1" / "user_api.py").read_text(
                encoding="utf-8"
            )
            schema = (root / "schemas" / "user_schema.py").read_text(
                encoding="utf-8"
            )
            requirements = (root / "requirements.txt").read_text(encoding="utf-8")
            dependencies = (
                root / "api" / "v1" / "dependencies.py"
            ).read_text(encoding="utf-8")

            self.assertIn("class Usuario(SQLModel, table=True)", model)
            self.assertIn("hashed_password=get_password_hash(user_data.password)", endpoint)
            self.assertNotIn("hashed_password:", schema)
            self.assertIn("fastapi[standard]", requirements)
            self.assertIn("sqlmodel", requirements)
            self.assertIn("email-validator", requirements)
            self.assertIn("python-jose[cryptography]", requirements)
            self.assertIn("python-multipart", requirements)
            self.assertIn("class UserUpdate(SQLModel):", schema)
            self.assertIn(
                "password: str = Field(min_length=8, max_length=72)",
                schema,
            )
            self.assertIn('tokenUrl="/api/v1/users/token"', dependencies)
            self.assertIn("@router.post(\"/token\"", endpoint)
            self.assertIn("Depends(get_current_user)", endpoint)
            self.assertIn("@router.put(\"/{user_id}\"", endpoint)
            self.assertIn("@router.delete(\"/{user_id}\"", endpoint)

            for source in root.rglob("*.py"):
                compile(source.read_text(encoding="utf-8"), str(source), "exec")
            self.assertTrue((root / "api" / "v1" / "user_api.py").is_file())
            self.assertTrue((root / "core" / "config.py").is_file())
            self.assertTrue(
                all("\\" not in relative_path for relative_path in PROJECT_TEMPLATES)
            )

    def test_alembic_scaffold_respects_option_and_generates_template(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = make_config(use_alembic=True)
            write_project_files(root, config, create_user_structure=False)

            self.assertTrue((root / "alembic.ini").is_file())
            self.assertTrue((root / "alembic" / "env.py").is_file())
            self.assertTrue((root / "alembic" / "script.py.mako").is_file())
            migration_template = (
                root / "alembic" / "script.py.mako"
            ).read_text(encoding="utf-8")
            self.assertIn("import sqlmodel", migration_template)
            self.assertTrue((root / "models" / "user_model.py").is_file())
            alembic_ini = (root / "alembic.ini").read_text(encoding="utf-8")
            alembic_env = (root / "alembic" / "env.py").read_text(
                encoding="utf-8"
            )
            self.assertIn("script_location = %(here)s/alembic", alembic_ini)
            self.assertIn("settings.DATABASE_URL", alembic_env)
            self.assertIn("target_metadata = SQLModel.metadata", alembic_env)
            self.assertIn("from models import user_model", alembic_env)
            self.assertFalse(
                list((root / "alembic" / "versions").glob("*.py")),
                "The initial revision must be created after the DB is available.",
            )
            self.assertIn(
                "USE_ALEMBIC=true",
                (root / ".env").read_text(encoding="utf-8"),
            )

    def test_project_name_is_requested_before_normalization(self) -> None:
        with patch("builtins.input", return_value="My New API"):
            self.assertEqual(_get_project_name(), "my_new_api")

    def test_project_directory_is_created_under_source_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_root = Path(temporary_directory)

            project_root = _create_project_directory(source_root, "sample_api")

            self.assertEqual(project_root, source_root / "sample_api")
            self.assertTrue(project_root.is_dir())

    def test_existing_nonempty_project_directory_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_root = Path(temporary_directory)
            project_root = source_root / "sample_api"
            project_root.mkdir()
            marker = project_root / "keep.txt"
            marker.write_text("keep", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                _create_project_directory(source_root, "sample_api")

            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
