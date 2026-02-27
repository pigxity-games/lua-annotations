from lua_annotations.exceptions import ParseError

#[val1, val2, val3]
def list_arg(string: str) -> list[str]:
    """Converts a string wrapped in [] and seperated by commas into a python list"""
    if not (string.startswith('[') and string.endswith(']')):
        raise ParseError('list argument must be wrapped in `[` and `]` characters')
    string = string[1:-1]
    if string.strip() == '':
        return []

    return [s.strip() for s in string.split(',')]

def default_list(str: str):
    """Tries to call list_arg, but if the argument cannot be parsed into a list, a list wrapped with the string is returned."""
    try:
        return list_arg(str)
    except ParseError:
        return [str]

def literal_builder(options: list[str]):
    def f(s: str):
        if s not in options:
            raise ParseError(f'{s!r} not in literal options: {options}')
        return s
    return f
