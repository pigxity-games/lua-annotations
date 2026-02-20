from exceptions import ParseError

#[val1, val2, val3]
def list_arg(string: str) -> list[str]:
    if not (string.startswith('[') and string.endswith(']')):
        raise ParseError('list argument must be wrapped in `[` and `]` characters')
    string = string[1:-1]
    if string.strip() == '':
        return []

    return [s.strip() for s in string.split(',')]

def literal_builder(options: list[str]):
    def f(s: str):
        if s not in options:
            raise ParseError(f'{s!r} not in literal options: {options}')
        return s
    return f
