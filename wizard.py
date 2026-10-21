#!/usr/bin/env python3
"""Entry point for the FastAPI project setup wizard."""

import argparse
import re
from pathlib import Path

from fastapi_wizard.environment import prepare_environment


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Asistente para crear proyectos FastAPI.")
    parser.add_argument("--project-name", help=argparse.SUPPRESS)
    parser.add_argument("--project-root", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def _get_project_name() -> str:
    raw_name = input("Nombre del proyecto (ej: mi_api): ").strip()
    project_name = raw_name.lower().replace(" ", "_")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project_name):
        raise ValueError(
            "El nombre del proyecto solo puede contener letras minúsculas, "
            "números, guiones y guiones bajos."
        )
    return project_name


def _create_project_directory(source_root: Path, project_name: str) -> Path:
    project_root = source_root / project_name
    if project_root.exists():
        if not project_root.is_dir() or any(project_root.iterdir()):
            raise FileExistsError(
                f"La carpeta '{project_root}' ya existe y contiene archivos. "
                "Elige otro nombre para evitar sobrescribirlos."
            )
    else:
        project_root.mkdir(parents=True)
    return project_root


def main() -> None:
    args = _parse_args()
    source_root = Path(__file__).resolve().parent
    script_path = Path(__file__).resolve()

    if args.project_root is not None and args.project_name:
        project_root = args.project_root.resolve()
        project_name = args.project_name
    else:
        project_name = _get_project_name()
        project_root = _create_project_directory(source_root, project_name)

    prepare_environment(
        project_root,
        script_path,
        source_root / "requirements.txt",
        project_name,
    )

    from fastapi_wizard.cli import run_wizard

    run_wizard(project_root, project_name)


if __name__ == "__main__":
    main()
