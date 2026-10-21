import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi_wizard import environment


class ActivatedShellTests(unittest.TestCase):
    @unittest.skipUnless(environment.os.name == "nt", "Windows-specific shell")
    def test_opens_new_console_in_project_with_virtual_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory) / "sample project"
            environment_dir = project_root / ".venv" / "Scripts"
            environment_dir.mkdir(parents=True)
            activation_script = environment_dir / "activate.bat"
            activation_script.touch()

            with patch.object(environment.subprocess, "Popen") as popen:
                environment.open_activated_shell(project_root)

            popen.assert_called_once()
            args, kwargs = popen.call_args
            self.assertEqual(
                args[0],
                f'cmd.exe /K ""{activation_script}" & cd /d "{project_root}""',
            )
            self.assertEqual(kwargs["cwd"], project_root)
            self.assertEqual(
                kwargs["creationflags"],
                subprocess.CREATE_NEW_CONSOLE,
            )

    def test_posix_shell_activation_quotes_project_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory) / "sample project"
            (project_root / ".venv" / "bin").mkdir(parents=True)

            with (
                patch.object(environment.os, "name", "posix"),
                patch.dict(environment.os.environ, {"SHELL": "/bin/zsh"}),
                patch.object(environment.subprocess, "run") as run,
            ):
                environment.open_activated_shell(project_root)

            args, kwargs = run.call_args
            command = args[0][2]
            self.assertEqual(args[0][0], "/bin/zsh")
            self.assertEqual(args[0][1], "-c")
            self.assertIn(f"'{project_root}", command)
            self.assertIn("activate", command)
            self.assertIn("exec /bin/zsh -i", command)
            self.assertEqual(kwargs["cwd"], project_root)

    def test_fish_uses_its_own_activation_script(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory) / "sample project"
            (project_root / ".venv" / "bin").mkdir(parents=True)

            with (
                patch.object(environment.os, "name", "posix"),
                patch.dict(environment.os.environ, {"SHELL": "/usr/bin/fish"}),
                patch.object(environment.subprocess, "run") as run,
            ):
                environment.open_activated_shell(project_root)

            command = run.call_args.args[0][2]
            self.assertIn("activate.fish", command)
            self.assertIn("and exec /usr/bin/fish -i", command)

    def test_bootstrap_checks_image_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            environment_dir = root / ".venv"
            environment_dir.mkdir()
            python_executable = environment._venv_python(environment_dir)
            python_executable.parent.mkdir(parents=True, exist_ok=True)
            python_executable.touch()
            requirements = root / "requirements.txt"
            requirements.write_text("pillow>=10,<13\n", encoding="utf-8")

            with (
                patch.object(environment, "_dependencies_are_installed", return_value=False),
                patch.object(environment.venv.EnvBuilder, "create"),
                patch.object(environment.subprocess, "run") as run,
                patch.object(environment.sys, "prefix", str(environment_dir)),
            ):
                environment.prepare_environment(
                    root,
                    root / "wizard.py",
                    requirements,
                    "sample",
                )

            self.assertEqual(run.call_count, 1)
            self.assertIn(str(requirements), run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
