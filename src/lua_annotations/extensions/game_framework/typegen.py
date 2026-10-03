# Resolves the source context needed by generated service declarations.
# Keeping imports and declared fields here prevents callers from compensating for incomplete generated types.

import re

from lua_annotations.api.lua_dict import LuaPath, LuaPathResolver
from lua_annotations.build_process import Environment
from lua_annotations.parser import split_top_level_csv
from lua_annotations.parser_schemas import LuaMethod, LuaModule

# Matches a local assignment; group 1 is its name and the match ends at the expression start.
LOCAL_BINDING_REGEX = re.compile(r'^local\s+(\w+)\s*(?::[^=\n]+)?=\s*', re.MULTILINE)

# Matches a type declaration; group 1 is its name and the match ends at the type body start.
TYPE_DECLARATION_REGEX = re.compile(r'^(?:export\s+)?type\s+(\w+)\s*=\s*', re.MULTILINE)

# Matches a colon method-call prefix to distinguish calls from type labels; no capture groups.
METHOD_CALL_REGEX = re.compile(r':\w+\s*\(')

# Matches a require-call prefix within a binding expression; no capture groups.
REQUIRE_CALL_REGEX = re.compile(r'\brequire\s*\(')

# Matches an entire signed integer or decimal literal; no capture groups.
NUMBER_LITERAL_REGEX = re.compile(r'-?\d+(?:\.\d+)?')

# Matches a local module assignment; group 1 is its name and the match ends at its initializer.
MODULE_INITIALIZER_REGEX = re.compile(r'^local\s+(\w+)\s*=\s*', re.MULTILINE)

# Matches an entire initializer entry; group 1 is the field name and group 2 is its expression.
FIELD_ENTRY_REGEX = re.compile(r'(\w+)\s*=\s*(.*)', re.DOTALL)

# Matches a module field assignment; group 1 is the module name and group 2 is the field name.
MODULE_FIELD_REGEX = re.compile(r'^(\w+)\.(\w+)\s*=\s*', re.MULTILINE)

# Matches quoted strings or comments; group 0 identifies the token so only comments are removed.
COMMENT_TOKEN_REGEX = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|--\[\[[\s\S]*?\]\]|--[^\n]*')

# Matches quoted strings, cast operators, or delimiters; group 0 supplies each nesting token.
CAST_TOKEN_REGEX = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|::|[(){}\[\]]')

# Matches quoted strings or unqualified identifiers; group 0 supplies the token to preserve or rebase.
IDENTIFIER_TOKEN_REGEX = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|(?<![\w.:])\b[A-Za-z_]\w*\b')

# Matches strings or qualified type references; groups 1 and 2 are the binding and type names, absent for strings.
SERVICE_TYPE_REFERENCE_REGEX = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b(\w+)\.(\w+)')


def _strip_comments(text: str):
    return COMMENT_TOKEN_REGEX.sub(
        lambda match: '' if match.group(0).startswith('--') else match.group(0),
        text,
    )


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

    for match in CAST_TOKEN_REGEX.finditer(value):
        token = match.group(0)

        match token:
            case '::' if depth == 0:
                return value[match.end() :].strip()
            case '(' | '{' | '[':
                depth += 1
            case ')' | '}' | ']':
                depth -= 1

    return None


class SourceTypes:
    """Renders public types with only the source imports and aliases they actually use."""

    def __init__(self, module: LuaModule, resolver: LuaPathResolver, env: Environment):
        self.env = env
        self.module = module
        self.resolver = resolver
        self.text = _strip_comments(module.file.read_text())

        self.bindings = {match.group(1): _expression(self.text, match.end()) for match in LOCAL_BINDING_REGEX.finditer(self.text)}
        self.types = {match.group(1): _expression(self.text, match.end()) for match in TYPE_DECLARATION_REGEX.finditer(self.text)}

        self.imports: dict[str, str] = {}
        self.aliases: dict[str, str] = {}

    def _name(self, name: str):
        return f'_{self.env.capitalize()}{self.module.returned_name}_{name}'

    def _source_expression(self, text: str, active: frozenset[str] = frozenset()):
        def replace(match: re.Match[str]):
            name = match.group(0)

            if name == 'script':
                return LuaPath(self.module.file).to_lua(
                    self.resolver,
                    inline_require=True,
                )

            value = self.bindings.get(name)

            if value is None or name in active:
                return name

            return self._source_expression(value, active | {name})

        return self._identifiers(text, replace)

    @staticmethod
    def _identifiers(text: str, replace):
        # Strings and property names are data, not source-local identifiers.
        def token(match: re.Match[str]):
            value = match.group(0)
            suffix = text[match.end() :].lstrip()
            label = suffix.startswith(':') and not suffix.startswith('::') and not METHOD_CALL_REGEX.match(suffix)

            if value[0] in ('"', "'") or label or (suffix.startswith('=') and not suffix.startswith('==')):
                return value

            return replace(match)

        return IDENTIFIER_TOKEN_REGEX.sub(token, text)

    def resolve(self, text: str, expression: bool = False):
        """Rebase a type or typeof expression into the generated module's scope."""

        def replace(match: re.Match[str]):
            name = match.group(0)

            if not expression and name in (self.module.name, self.module.returned_name):
                return self.module.returned_name

            binding = self.bindings.get(name, '')

            if REQUIRE_CALL_REGEX.search(binding):
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
                # Only this generated-types binding is removed; strings and other qualifiers stay intact.
                text = SERVICE_TYPE_REFERENCE_REGEX.sub(
                    lambda match: match.group(2) if match.group(1) == name else match.group(0),
                    text,
                )

        return self._identifiers(text, replace)

    def _field_type(self, value: str):
        cast = _outer_cast(value)

        if cast is not None:
            return self.resolve(cast)

        match value:
            case 'true' | 'false':
                return 'boolean'

            case _ if NUMBER_LITERAL_REGEX.fullmatch(value):
                return 'number'

            case _ if value.startswith(('"', "'")):
                return 'string'

            case 'nil':
                return 'nil'

            case _:
                return f'typeof({self.resolve(value, expression=True)})'

    def fields(self):
        """Read initializer entries and explicitly declared public module fields."""
        fields: dict[str, str] = {}
        start = next(
            (match for match in MODULE_INITIALIZER_REGEX.finditer(self.text) if match.group(1) == self.module.name),
            None,
        )

        if start:
            value = _expression(self.text, start.end())

            if value.startswith('{') and value.endswith('}'):
                for entry in split_top_level_csv(value[1:-1]):
                    match = FIELD_ENTRY_REGEX.fullmatch(entry)

                    if match:
                        fields[match.group(1)] = match.group(2)

        for match in MODULE_FIELD_REGEX.finditer(self.text):
            if match.group(1) == self.module.name:
                fields[match.group(2)] = _expression(self.text, match.end())

        return {name: self._field_type(value) for name, value in fields.items() if not name.startswith('_') and name not in self.module.methods}

    def method(
        self,
        method: LuaMethod,
        params: list[str] | None = None,
        return_type: str | None = None,
    ):
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
        methods = [f'    {name}: {self.method(method)},' for name, method in self.module.methods.items() if not name.startswith('_')]

        return '{\n' + '\n'.join(fields + methods) + '\n}'

    def prelude(self):
        """Return the imports and aliases reached while rendering this module."""

        return [f'local {name} = {expr}' for name, expr in self.imports.items()] + [f'type {name} = {data}' for name, data in self.aliases.items()]
