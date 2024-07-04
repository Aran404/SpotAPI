from colorama import Fore, Style, init
from spotify.types.interfaces import LoggerProtocol
from datetime import datetime
import os
import time

init(autoreset=True)


class Logger(LoggerProtocol):
    @staticmethod
    def __fmt_time() -> str:
        t = datetime.now().strftime("%H:%M:%S")
        return f"[{Style.BRIGHT}{Fore.BLUE}{str(t)}{Style.RESET_ALL}]"

    @staticmethod
    def error(s: str, **extra) -> None:
        fields = [
            f"{Fore.LIGHTBLACK_EX}{k}={Fore.LIGHTBLACK_EX}{v}" for k, v in extra.items()
        ]
        print(
            f"{Logger.__fmt_time()} {Style.BRIGHT}{Fore.RED}{s}{Style.RESET_ALL} "
            + " ".join(fields)
        )

    @staticmethod
    def info(s: str, **extra) -> None:
        fields = [
            f"{Fore.LIGHTBLACK_EX}{k}={Fore.LIGHTBLACK_EX}{v}" for k, v in extra.items()
        ]
        print(
            f"{Logger.__fmt_time()} {Style.BRIGHT}{Fore.MAGENTA}{s}{Style.RESET_ALL} "
            + " ".join(fields)
        )

    @staticmethod
    def fatal(s: str, **extra) -> None:
        fields = [
            f"{Fore.LIGHTBLACK_EX}{k}={Fore.LIGHTBLACK_EX}{v}" for k, v in extra.items()
        ]
        print(
            f"{Logger.__fmt_time()} {Style.BRIGHT}{Fore.RED}{s}{Style.RESET_ALL} "
            + " ".join(fields)
        )
        time.sleep(5)
        os._exit(1)


class NoopLogger(LoggerProtocol):
    @staticmethod
    def error(s: str, **extra) -> None:
        ...

    @staticmethod
    def info(s: str, **extra) -> None:
        ...

    @staticmethod
    def fatal(s: str, **extra) -> None:
        ...
