# Resolves the source context needed by generated service declarations.
# Keeping imports and declared fields here prevents callers from compensating for incomplete generated types.
import re

from lua_annotations.api.lua_dict import LuaPath, LuaPathResolver
from lua_annotations.build_process import Environment
from lua_annotations.parser import split_top_level_csv
from lua_annotations.parser_schemas import LuaMethod, LuaModule


def _strip_comments(text: str):
    pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|--\[\[[\s\S]*?\]\]|--[^\n]*'
    return re.sub(pattern, lambda match: '' if match.group(0).startswith('--') else match.group(0), text)


def _expression(text: str, start: int):
    stack = []
    quote = None
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char in '({[':
            stack.append(char)
        elif char in ')}]':
            if not stack:
                return text[start:index].strip()
            stack.pop()
        elif char == '\n' and not stack:
            return text[start:index].strip()
    return text[start:].strip()


def _outer_cast(value: str):
    depth = 0
    pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|::|[(){}\[\]]'
    for match in re.finditer(pattern, value):
        token = match.group(0)
        if token == '::' and depth == 0:
            return value[match.end():].strip()
        if token in ('(', '{', '['):
            depth += 1
        elif token in (')', '}', ']'):
            depth -= 1
    return None


class SourceTypes:
    """Renders public types with only the source imports and aliases they actually use."""

    def __init__(self, module: LuaModule, resolver: LuaPathResolver, env: Environment):
        self.env = env
        self.module = module
        self.resolver = resolver
        self.text = _strip_comments(module.file.read_text())
        self.bindings = {
            match.group(1): _expression(self.text, match.end())
            for match in re.finditer(r'^local\s+(\w+)\s*(?::[^=\n]+)?=\s*', self.text, re.MULTILINE)
        }
        self.types = {
            match.group(1): _expression(self.text, match.end())
            for match in re.finditer(r'^(?:export\s+)?type\s+(\w+)\s*=\s*', self.text, re.MULTILINE)
        }
        self.imports: dict[str, str] = {}
        self.aliases: dict[str, str] = {}

    def _name(self, name: str):
        return f'_{self.env.capitalize()}{self.module.returned_name}_{name}'

    def _source_expression(self, text: str, active: frozenset[str] = frozenset()):
        def replace(match: re.Match[str]):
            name = match.group(0)
            if name == 'script':
                return LuaPath(self.module.file).to_lua(self.resolver, inline_require=True)
            value = self.bindings.get(name)
            if value is None or name in active:
                return name
            return self._source_expression(value, active | {name})

        return self._identifiers(text, replace)

    @staticmethod
    def _identifiers(text: str, replace):
        # Strings and property names are data, not source-local identifiers.
        pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|(?<![\w.:])\b[A-Za-z_]\w*\b'
        def token(match: re.Match[str]):
            value = match.group(0)
            suffix = text[match.end():].lstrip()
            label = (suffix.startswith(':') and not suffix.startswith('::')
                     and not re.match(r':\w+\s*\(', suffix))
            if value[0] in ('"', "'") or label or (suffix.startswith('=') and not suffix.startswith('==')):
                return value
            return replace(match)

        return re.sub(pattern, token, text)

    def resolve(self, text: str, expression: bool = False):
        """Rebase a type or typeof expression into the generated module's scope."""
        def replace(match: re.Match[str]):
            name = match.group(0)
            if not expression and name in (self.module.name, self.module.returned_name):
                return self.module.returned_name
            binding = self.bindings.get(name, '')
            if re.search(r'\brequire\s*\(', binding):
                if 'Generated.ServiceTypes' in binding:
                    return ''
                alias = self._name(name)
                self.imports.setdefault(alias, self._source_expression(binding))
                return alias
            if name in self.types:
                alias = self._name(name)
                if alias not in self.aliases:
                    # Reserve the alias first so recursive types terminate.
                    self.aliases[alias] = ''
                    data = self.resolve(self.types[name])
                    self.aliases.pop(alias)
                    self.aliases[alias] = data
                return alias
            if binding:
                return self.resolve(binding, expression)
            return name

        for name, binding in self.bindings.items():
            if 'Generated.ServiceTypes' in binding:
                pattern = rf'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b{re.escape(name)}\.(\w+)'
                text = re.sub(pattern, lambda match: match.group(1) or match.group(0), text)
        return self._identifiers(text, replace)

    def _field_type(self, value: str):
        cast = _outer_cast(value)
        if cast is not None:
            return self.resolve(cast)
        if value in ('true', 'false'):
            return 'boolean'
        if re.fullmatch(r'-?\d+(?:\.\d+)?', value):
            return 'number'
        if value.startswith(('"', "'")):
            return 'string'
        if value == 'nil':
            return 'nil'
        return f'typeof({self.resolve(value, expression=True)})'

    def fields(self):
        """Read initializer entries and explicitly declared public module fields."""
        fields: dict[str, str] = {}
        start = re.search(rf'^local\s+{re.escape(self.module.name)}\s*=\s*', self.text, re.MULTILINE)
        if start:
            value = _expression(self.text, start.end())
            if value.startswith('{') and value.endswith('}'):
                for entry in split_top_level_csv(value[1:-1]):
                    match = re.fullmatch(r'(\w+)\s*=\s*(.*)', entry, re.DOTALL)
                    if match:
                        fields[match.group(1)] = match.group(2)
        for match in re.finditer(rf'^{re.escape(self.module.name)}\.(\w+)\s*=\s*', self.text, re.MULTILINE):
            fields[match.group(1)] = _expression(self.text, match.end())
        return {
            name: self._field_type(value)
            for name, value in fields.items()
            if not name.startswith('_') and name not in self.module.methods
        }

    def method(self, method: LuaMethod, params: list[str] | None = None, return_type: str | None = None):
        """Render a method after any sender-specific parameter transformation."""
        values = params if params is not None else list(method.params.values())
        values = [self.resolve(value) for value in values]
        if params is None and method.call_type == ':':
            # Self names the generated type, not the source-local table binding.
            values = [self.module.returned_name] + values
        result = method.return_type if return_type is None else return_type
        result = result if result != 'nil' else ''
        return f'({", ".join(values)}) -> ({self.resolve(result)})'

    def declaration(self):
        """Render the local module's declared fields and public methods."""
        fields = [f'    {name}: {data},' for name, data in self.fields().items()]
        methods = [
            f'    {name}: {self.method(method)},'
            for name, method in self.module.methods.items()
            if not name.startswith('_')
        ]
        return '{\n' + '\n'.join(fields + methods) + '\n}'

    def prelude(self):
        """Return the imports and aliases reached while rendering this module."""
        return [f'local {name} = {expr}' for name, expr in self.imports.items()] + [
            f'type {name} = {data}' for name, data in self.aliases.items()
        ]
