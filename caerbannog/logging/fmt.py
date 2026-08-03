from .ansi import FG_BLUE, FG_BRIGHT_BLACK, FG_CYAN_BOLD, FG_RESET, RESET


def target(content: str) -> str:
    if content == "":
        content = "''"
    return f"{FG_CYAN_BOLD}{content}{RESET}"


def subject(content: str) -> str:
    if content == "":
        content = "''"
    return f"{FG_BLUE}{content}{FG_RESET}"


def code(content: str) -> str:
    if content == "":
        content = "''"
    return f"{FG_BRIGHT_BLACK}{content}{FG_RESET}"
