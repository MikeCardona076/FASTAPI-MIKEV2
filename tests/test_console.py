import io
import unittest
from contextlib import redirect_stdout

from fastapi_wizard.console import clear_screen, pixel_art


class ConsoleTests(unittest.TestCase):
    def test_pixel_art_renders_true_color_blocks(self) -> None:
        rendered = pixel_art(width=8)

        self.assertIn("\033[38;2;", rendered)
        self.assertIn("\033[48;2;", rendered)
        self.assertIn("▀", rendered)

    def test_clear_screen_emits_terminal_clear_and_home(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            clear_screen()

        self.assertEqual(output.getvalue(), "\033[0m\033[2J\033[H")


if __name__ == "__main__":
    unittest.main()
