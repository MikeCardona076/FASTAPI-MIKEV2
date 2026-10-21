from pathlib import Path
import subprocess
import sys

from fastapi_wizard.console import (
    clear_screen,
    info,
    show_banner,
    success,
    title,
    warning,
)
from fastapi_wizard.environment import open_activated_shell
from fastapi_wizard.generation import write_project_files
from fastapi_wizard.prompts import WizardCancelled, collect_config


def run_wizard(project_root: Path, project_name: str) -> None:
    clear_screen()
    show_banner()
    title("🚀 Asistente de Inicialización")
    title("=" * 60)

    try:
        config, use_alembic, create_user_structure = collect_config(project_name)
    except WizardCancelled:
        warning("Inicialización cancelada.")
        return

    info("\n⚙️  Generando archivos de configuración...")
    write_project_files(project_root, config, create_user_structure)
    success("Carpeta './minio_data' preparada para MinIO.")
    info("Instalando las dependencias del proyecto en .venv...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(project_root / "requirements.txt"),
        ],
        cwd=project_root,
        check=True,
    )

    if create_user_structure or config.use_alembic:
        success(
            "Aplicación FastAPI creada con modelo Usuario y registro "
            "con contraseña hasheada."
        )

    if use_alembic:
        success("Configuración de Alembic creada.")

    title("\n" + "=" * 60)
    success("✅ ¡Proyecto inicializado con éxito!")
    info("👉 Siguientes pasos:")
    info("   1. Revisa los archivos .env y docker-compose.yml")
    if use_alembic:
        info("   2. Inicia los servicios: docker compose up -d")
        info("   3. Espera a que la base de datos esté lista.")
        info('   4. Crea la migración: alembic revision --autogenerate -m "initial"')
        info("   5. Crea las tablas en la base: alembic upgrade head")
        info("   6. Después inicia la API: fastapi dev")
    else:
        info("   2. Inicia los servicios: docker compose up -d")
    if create_user_structure or use_alembic:
        if not use_alembic:
            info("   3. Inicia la API: fastapi dev")
    title("=" * 60)

    open_activated_shell(project_root)
