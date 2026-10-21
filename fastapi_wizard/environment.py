import os
import shlex
import subprocess
import sys
import venv
from pathlib import Path


def _venv_python(environment_dir: Path) -> Path:
    if os.name == "nt":
        return environment_dir / "Scripts" / "python.exe"
    return environment_dir / "bin" / "python"


def _dependencies_are_installed(python_executable: Path) -> bool:
    result = subprocess.run(
        [
            str(python_executable),
            "-c",
            "import colorama, questionary",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def prepare_environment(
    project_root: Path,
    script_path: Path,
    requirements: Path,
    project_name: str,
) -> None:
    environment_dir = project_root / ".venv"

    if not environment_dir.exists():
        print("Creando el entorno virtual .venv...")
        venv.EnvBuilder(with_pip=True).create(environment_dir)

    python_executable = _venv_python(environment_dir)
    if not python_executable.is_file():
        raise FileNotFoundError(
            f"No se encontró el Python del entorno virtual: {python_executable}"
        )

    if not _dependencies_are_installed(python_executable):
        if not requirements.is_file():
            raise FileNotFoundError(f"No se encontró el archivo: {requirements}")
        print("Instalando las dependencias del asistente...")
        subprocess.run(
            [
                str(python_executable),
                "-m",
                "pip",
                "install",
                "-r",
                str(requirements),
            ],
            cwd=project_root,
            check=True,
        )

    if Path(sys.prefix).resolve() != environment_dir.resolve():
        print("Entorno virtual listo. Iniciando el wizard dentro de .venv...")
        subprocess.run(
            [
                str(python_executable),
                str(script_path),
                "--project-name",
                project_name,
                "--project-root",
                str(project_root),
            ],
            cwd=project_root,
            check=True,
        )
        raise SystemExit(0)


def open_activated_shell(project_root: Path) -> None:
    environment_dir = project_root / ".venv"

    if os.name == "nt":
        activate_script = environment_dir / "Scripts" / "activate.bat"
        print(
            "Abriendo una consola de Windows con .venv activado. "
            "Escribe exit para cerrarla."
        )
        command_line = (
            f'cmd.exe /K ""{activate_script}" & cd /d "{project_root}""'
        )
        subprocess.Popen(
            command_line,
            cwd=project_root,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        return

    activate_script = environment_dir / "bin" / "activate"
    shell = os.environ.get("SHELL", "/bin/bash")
    shell_name = Path(shell).name
    if shell_name == "fish":
        activate_script = environment_dir / "bin" / "activate.fish"
        command = (
            f"source {shlex.quote(str(activate_script))}; "
            f"and exec {shlex.quote(shell)} -i"
        )
    else:
        command = (
            f". {shlex.quote(str(activate_script))} && "
            f"exec {shlex.quote(shell)} -i"
        )
    print("Abriendo una consola con .venv activado. Escribe exit para cerrarla.")
    subprocess.run([shell, "-c", command], cwd=project_root, check=False)
