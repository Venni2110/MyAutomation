import colorama

# Initialize colorama (enables ANSI codes on Windows)
colorama.init(autoreset=True)

from colorama import Fore, Style

def print_info(msg: str):
    '''Prints an informational message in green.'''
    print(f"{Fore.GREEN}[INFO]{Style.RESET_ALL} {msg}")

def print_warning(msg: str):
    '''Prints a warning message in yellow.'''
    print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {msg}")

def print_error(msg: str):
    '''Prints an error message in red.'''
    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {msg}")
