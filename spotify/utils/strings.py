def parse_json_string(b: str, s: str) -> str:
    start_index = b.find(f'{s}":"')
    if start_index == -1:
        raise ValueError(f'Substring "{s}":" not found in JSON string')

    value_start_index = start_index + len(s) + 3
    value_end_index = b.find('"', value_start_index)
    if value_end_index == -1:
        raise ValueError(f'Closing double quote not found after "{s}":"')

    return b[value_start_index:value_end_index]
