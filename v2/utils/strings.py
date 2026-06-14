import string
import random
import base64
import ast
import os
import re

__all__: tuple[str, ...] = (
    "random_b64_string",
    "random_hex_string",
    "parse_json_string",
    "random_string",
    "random_domain",
    "random_email",
    "random_dob",
    "random_nonce",
    "extract_mappings",
    "combine_chunks",
    "extract_js_links",
    "extract_query_hashes",
)


def extract_mappings(js_code: str) -> tuple[dict[int, str], dict[int, str]]:
    pattern = r"\{\d+:\"[^\"]+\"(?:,\d+:\"[^\"]+\")*\}"
    matches = re.findall(pattern, js_code)

    if len(matches) < 2:
        raise ValueError("Could not find both mappings in the JS code.")

    mapping1 = ast.literal_eval(matches[3])
    mapping2 = ast.literal_eval(matches[4])

    return mapping1, mapping2


def combine_chunks(name_map: dict[int, str], hash_map: dict[int, str]) -> list[str]:
    combined: list[str] = []
    for key in name_map:
        if key in hash_map:
            filename = f"{name_map[key]}.{hash_map[key]}.js"
            combined.append(filename)
    return combined


def extract_js_links(html_content: str) -> list[str]:
    """Extract all absolute .js links (http/https) from HTML content using regex."""
    pattern = r'["\'](https?://[^"\']+\.js(?:\?[^"\']*)?)["\']'
    matches = re.findall(pattern, html_content, re.IGNORECASE)
    return list(filter(lambda s: "spotify" in s, set(matches)))


def extract_query_hashes(content: str) -> dict[str, str]:
    pattern = r'"([^"]+)",\s*"query",\s*"([^"]+)"'
    matches = re.findall(pattern, content)
    return {key: value for key, value in matches}


def random_b64_string(length: int) -> str:
    """Used by Spotify internally"""

    def generate_random_string(length: int) -> str:
        random_string = "".join(chr(random.randint(0, 255)) for _ in range(length))
        return random_string

    random_string = generate_random_string(length)
    encoded_string = base64.b64encode(random_string.encode("latin1")).decode("ascii")

    return encoded_string


def random_hex_string(length: int):
    """Used by Spotify internally"""
    num_bytes = (length + 1) // 2
    random_bytes = os.urandom(num_bytes)
    hex_string = random_bytes.hex()
    return hex_string[:length]


def parse_json_string(b: str, s: str) -> str:
    start_index = b.find(f'{s}":"')
    if start_index == -1:
        raise ValueError(f'Substring "{s}":" not found in JSON string')

    value_start_index = start_index + len(s) + 3
    value_end_index = b.find('"', value_start_index)
    if value_end_index == -1:
        raise ValueError(f'Closing double quote not found after "{s}":"')

    return b[value_start_index:value_end_index]


def random_string(length: int, /, strong: bool = False) -> str:
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


def random_nonce() -> str:
    return "".join(str(random.getrandbits(32)) for _ in range(2))
