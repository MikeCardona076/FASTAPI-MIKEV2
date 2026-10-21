from colorama import Fore, Style, init


init(autoreset=True)


def title(message: str) -> None:
    print(Fore.CYAN + Style.BRIGHT + message)


def success(message: str) -> None:
    print(Fore.GREEN + Style.BRIGHT + message)


def info(message: str) -> None:
    print(Fore.BLUE + message)


def warning(message: str) -> None:
    print(Fore.YELLOW + message)
