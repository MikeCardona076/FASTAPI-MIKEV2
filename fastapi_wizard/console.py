from pathlib import Path

from colorama import Fore, Style, just_fix_windows_console
from PIL import Image


just_fix_windows_console()

ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "fastapi-mike-icon.png"


def title(message: str) -> None:
    print(Fore.CYAN + Style.BRIGHT + message + Style.RESET_ALL)


def success(message: str) -> None:
    print(Fore.GREEN + Style.BRIGHT + message + Style.RESET_ALL)


def info(message: str) -> None:
    print(Fore.BLUE + message + Style.RESET_ALL)


def warning(message: str) -> None:
    print(Fore.YELLOW + message + Style.RESET_ALL)


def clear_screen() -> None:
    print("\033[0m\033[2J\033[H", end="", flush=True)


def pixel_art(image_path: Path = ICON_PATH, width: int = 28) -> str:
    image = Image.open(image_path).convert("RGB")
    height = max(1, round(image.height * width / image.width))
    image = image.resize((width, height), Image.Resampling.NEAREST)
    pixels = image.load()
    lines: list[str] = []

    for y in range(0, height, 2):
        line = []
        for x in range(width):
            top = pixels[x, y]
            bottom = pixels[x, y + 1] if y + 1 < height else (255, 255, 255)
            line.append(
                f"\033[38;2;{top[0]};{top[1]};{top[2]}m"
                f"\033[48;2;{bottom[0]};{bottom[1]};{bottom[2]}m▀"
            )
        line.append("\033[0m")
        lines.append("".join(line))
    return "\n".join(lines)


def show_banner() -> None:
    print(pixel_art())
    title("  FASTAPI MIKE")
    info("  Tu próximo proyecto empieza aquí.\n")
