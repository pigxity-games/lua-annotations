#[val1, val2, val3]

def list_arg(string: str) -> list[str]:
    assert string.startswith('[') and string.endswith(']')
    string = string[1:-1]
    if string.strip() == '':
        return []

    return [s.strip() for s in string.split(',')]

def literal_builder(options: list[str]):
    def f(s: str):
        if s not in options:
            raise ValueError(f'{s!r} not in literal options: {options}')
        return s
    return f
