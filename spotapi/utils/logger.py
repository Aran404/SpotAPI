import os
import time
from threading import Lock
from datetime import datetime
from colorama import Fore, Style, init
from spotapi.data import LoggerProtocol

os.system("")
init(autoreset=True)

# By convention we use the thread lock to ensure that we don't interfere with prints.
# If there are multiple instances of your program, you may need to use a custom logger implementation that doesn't rely on staticmethods
LOCK = Lock()


class Logger(LoggerProtocol):
    """
    A simple Stdout logger that can be used internally.
    """

    @staticmethod
    def __fmt_time() -> str:
        t = datetime.now().strftime("%H:%M:%S")
        return f"[{Style.BRIGHT}{Fore.LIGHTCYAN_EX}{str(t)}{Style.RESET_ALL}]"

    @staticmethod
    def error(s: str, **extra) -> None:
        with LOCK:
            fields = [
                f"{Style.BRIGHT}{Fore.LIGHTBLUE_EX}{k}={Fore.LIGHTRED_EX}{v}{Style.RESET_ALL}"
                for k, v in extra.items()
            ]
            print(
                f"{Logger.__fmt_time()} {Style.BRIGHT}{Style.RESET_ALL}{Fore.LIGHTRED_EX}{s} "
                + " ".join(fields)
            )

    @staticmethod
    def debug(s: str, **extra) -> None:
        with LOCK:
            fields = [
                f"{Style.BRIGHT}{Fore.LIGHTBLUE_EX}{k}={Fore.LIGHTYELLOW_EX}{v}{Style.RESET_ALL}"
                for k, v in extra.items()
            ]
            print(
                f"{Logger.__fmt_time()} {Style.BRIGHT}{Style.RESET_ALL}{Fore.LIGHTYELLOW_EX}{s} "
                + " ".join(fields)
            )

    @staticmethod
    def info(s: str, **extra) -> None:
        with LOCK:
            fields = [
                f"{Style.BRIGHT}{Fore.LIGHTBLUE_EX}{k}={Fore.LIGHTMAGENTA_EX}{v}{Style.RESET_ALL}"
                for k, v in extra.items()
            ]
            print(
                f"{Logger.__fmt_time()} {Style.BRIGHT}{Style.RESET_ALL}{Fore.LIGHTMAGENTA_EX}{s} "
                + " ".join(fields)
            )

    @staticmethod
    def fatal(s: str, **extra) -> None:
        with LOCK:
            fields = [
                f"{Style.BRIGHT}{Fore.LIGHTBLUE_EX}{k}={Fore.LIGHTRED_EX}{v}{Style.RESET_ALL}"
                for k, v in extra.items()
            ]
            print(
                f"{Logger.__fmt_time()} {Style.BRIGHT}{Style.RESET_ALL}{Fore.LIGHTRED_EX}{s} "
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

    @staticmethod
    def attempt(s: str, **extra) -> None:
        ...
