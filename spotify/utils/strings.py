import string
import random
from typing import Optional


def parse_json_string(b: str, s: str) -> str:
    start_index = b.find(f'{s}":"')
    if start_index == -1:
        raise ValueError(f'Substring "{s}":" not found in JSON string')

    value_start_index = start_index + len(s) + 3
    value_end_index = b.find('"', value_start_index)
    if value_end_index == -1:
        raise ValueError(f'Closing double quote not found after "{s}":"')

    return b[value_start_index:value_end_index]


def random_string(length: int, /, strong: Optional[bool] = False) -> str:
    letters = string.ascii_letters
    rnd = "".join(random.choice(letters) for _ in range(length))

    if strong:
        rnd += random.choice(string.digits)
        rnd += random.choice("@$%&*!?")

    return rnd


def random_domain() -> str:
    domains = [
        "gmail.com",
        "outlook.com",
        "yahoo.com",
        "hotmail.com",
        "aol.com",
        "comcast.net",
        "icloud.com",
        "msn.com",
        "live.com",
        "protonmail.com",
        "yandex.com",
        "tutanota.com",
    ]
    return random.choice(domains)


def random_email() -> str:
    return f"{random_string(10)}@{random_domain()}"


def random_dob() -> str:
    return f"{random.randint(1950, 2000)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
