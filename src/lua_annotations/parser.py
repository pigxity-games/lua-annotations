from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, TypeVar

from lua_annotations.build_process import logger

from .api.annotations import AnnotationBuildCtx, AnnotationDef, SortedRegistry
from .parser_schemas import *

if TYPE_CHECKING:
    from .build_process import BuildProcessCtx

# helper functions
K = TypeVar('K')
V = TypeVar('V')


def reverse_dict(d: dict[K, V]) -> dict[V, K]:
    return {v: k for k, v in d.items()}


def set_adornee(anots: list[Annotation], adornee: Adornee):
    for anot in anots:
        anot.adornee = adornee


def remove_whitespace(t: list[Any]):
    return [p.strip() for p in t]


def split_top_level_csv(text: str):
    parts: list[str] = []
    current: list[str] = []

    in_string: str | None = None
    escaped = False
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0

    for char in text:
        if in_string:
            current.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == in_string:
                in_string = None
            continue

        if char in ('"', "'"):
            in_string = char
            current.append(char)
            continue

        if char == '(':
            paren_depth += 1
        elif char == ')' and paren_depth > 0:
            paren_depth -= 1
        elif char == '{':
            brace_depth += 1
        elif char == '}' and brace_depth > 0:
            brace_depth -= 1
        elif char == '[':
            bracket_depth += 1
        elif char == ']' and bracket_depth > 0:
            bracket_depth -= 1

        if char == ',' and paren_depth == 0 and brace_depth == 0 and bracket_depth == 0:
            part = ''.join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue

        current.append(char)

    tail = ''.join(current).strip()
    if tail:
        parts.append(tail)

    return parts


def map_param_list(params: list[str]):
    out: dict[str, str] = {}
    for param in params:
        parts = remove_whitespace(param.split(':', 1))
        if len(parts) > 1:
            out[parts[0]] = parts[1]
        else:
            out[parts[0]] = 'any'

    return out


def split_qualified_name(name: str):
    for separator in ('.', ':'):
        if separator in name:
            module_name, function_name = name.split(separator, 1)
            return module_name, function_name, separator
    return None, name, ''


def _scan_balanced_parens(text: str, open_index: int):
    depth = 0
    in_string: str | None = None
    escaped = False

    for i in range(open_index, len(text)):
        char = text[i]

        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == in_string:
                in_string = None
            continue

        if char in ('"', "'"):
            in_string = char
            continue

        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                return i

    return None


def _collect_multiline_function_signature(code_line: str, lines: list[str], index: int) -> str:
    if not is_function_definition(code_line):
        return code_line

    open_paren = code_line.find('(')
    if open_paren == -1:
        return code_line

    if _scan_balanced_parens(code_line, open_paren) is not None:
        return code_line

    text = code_line
    for next_index in range(index + 1, len(lines)):
        next_line = lines[next_index]
        next_code = next_line.split('--')[0].rstrip()
        text += '\n' + next_code
        if _scan_balanced_parens(text, open_paren) is not None:
            return text

    return text


def _extract_signature_parts(text: str):
    open_paren = text.find('(')
    if open_paren == -1:
        return None

    close_paren = _scan_balanced_parens(text, open_paren)
    if close_paren is None:
        return None

    name_part = text[:open_paren].strip()
    raw_params = text[open_paren + 1 : close_paren]
    suffix = text[close_paren + 1 :].strip()
    return name_part, raw_params, suffix


def _parse_assignment_signature(text: str):
    assignment = re.match(r'^(.*?)=\s*function\b(.*)$', text)
    if not assignment:
        return None

    left = assignment.group(1).strip()
    right = assignment.group(2).lstrip()
    parts = _extract_signature_parts(right)
    if not parts:
        return None

    _, raw_params, suffix = parts
    return left, raw_params, suffix


def _parse_declaration_signature(text: str):
    for prefix in ('local function ', 'function '):
        if text.startswith(prefix):
            header = text.removeprefix(prefix).lstrip()
            return _extract_signature_parts(header)
    return None


def parse_function_signature(text: str):
    stripped = text.strip()
    if 'function' not in stripped:
        return None

    parsed = _parse_declaration_signature(stripped)
    if parsed:
        name_part, raw_params, suffix = parsed
    else:
        parsed = _parse_assignment_signature(stripped)
        if not parsed:
            return None

        name_part, raw_params, suffix = parsed

    module_name, function_name, call_type = split_qualified_name(name_part)
    if function_name == '':
        return None

    return_type = 'nil'
    if suffix.startswith(':'):
        return_type = suffix.removeprefix(':').strip() or 'nil'

    return module_name, function_name, call_type, raw_params, return_type


def unwrap_return_module(expr: str) -> str | None:
    cur = expr.strip()
    while True:
        direct = re.fullmatch(r'(\w+)', cur)
        if direct:
            return direct.group(1)

        wrapper = re.fullmatch(r'\w+\(\s*(.+)\s*\)', cur)
        if not wrapper:
            return None

        cur = wrapper.group(1).strip()


def is_literal_function(expr: str):
    return bool(re.match(r'^function\s*\(', expr.strip()))


def is_function_definition(text: str):
    stripped = text.strip()
    if stripped.startswith('function '):
        return True
    return bool(re.match(r'^\s*[\w.]+\s*[:=]\s*function\s*\(', stripped))


# parsing
@dataclass
class FileParser:
    reg: SortedRegistry
    file: Path
    build_ctx: 'BuildProcessCtx'
    annotations: list[Annotation] = field(default_factory=list)
    cur_annotations: list[Annotation] = field(default_factory=list)
    modules: dict[str, LuaModule] = field(default_factory=dict)
    types: dict[str, LuaType] = field(default_factory=dict)
    explicit_method_modules: set[str] = field(default_factory=set)
    implicit_method_names: dict[str, set[str]] = field(default_factory=dict)
    cur_line = 0

    def __post_init__(self):
        self.file_name: str = self.file.name.split('.')[0]

    # assertion functions
    def _check_anot_scopes(self, line: str, anots: list[AnnotationDef]):
        scope = anots[0].scope
        for anot in anots:
            if not anot.scope == scope:
                self.error(line, f'all annotations must have scope: `{scope}`')

    def _check_anot_relations(self, line: str, anots: list[AnnotationDef]):
        for anot in anots:
            for inc in anot.mutual_exclude:
                if inc in anots:
                    self.error(
                        line,
                        f'annotation {anot.name} excludes {inc.name}, but it is present in this code block',
                    )

            for inc in anot.mutual_include:
                if not inc in anots:
                    self.error(
                        line,
                        f'annotation {anot.name} requires {inc.name}, but it is not present in this code block',
                    )

    # parsing helpers
    def _parse_anot_args(self, adef: AnnotationDef, args: list[str]):
        kwargs_val: dict[str, Any] = {}
        args_val: list[Any] = []

        for i, arg in enumerate(args):
            if '=' in arg:
                name, val = [part.strip() for part in arg.split('=', 1)]
                proc = adef.kwargs[name]
                kwargs_val[name] = proc(val)
            else:
                proc = adef.args[i]
                args_val.append(proc(arg))

        return args_val, kwargs_val

    def _parse_annotation(self, text: str, ctx: SortedRegistry):
        parts = split_top_level_csv(text.removeprefix(ANNOTATION_PREFIX))
        name = parts[0]

        adef = ctx.anot_registry.get(name)
        if adef:
            args, kwargs = self._parse_anot_args(adef, parts[1:])
            return Annotation(adef, name, args, kwargs)
        else:
            self.error(text, 'Annotation does not exist')

    def _get_dict_data(self, text: str):
        text = text.strip()
        if text.startswith('{') and text.endswith('}'):
            text = text[1:-1]

        clean_lines: list[str] = []
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if stripped.startswith('--'):
                continue
            clean_lines.append(raw_line.split('--')[0])
        text = '\n'.join(clean_lines)

        entries = split_top_level_csv(text)
        if len(entries) == 0:
            self.error(text, 'line is not a dict')

        out: dict[str, str] = {}
        for entry in entries:
            match = RETURN_TABLE_ENTRY_REGEX.search(entry)
            if not match:
                self.error(entry, 'line is not a dict')

            key = match.group(1)
            value = match.group(2).strip()
            out[key] = value

        return out

    def _map_dict_return(self, k: str, v: Any) -> str:
        module_name = unwrap_return_module(v)
        if module_name:
            return module_name

        if is_literal_function(v):
            return k

        self.error(v, 'submodule export is incorrectly defined')

    def _get_returned(self, text: str, default_name: str):
        return_starts = list(re.finditer(r'^return\b', text, re.MULTILINE))
        if len(return_starts) == 0:
            return

        match = RETURN_REGEX.search(text[return_starts[-1].start() :])
        if not match:
            return

        single_expr: str = (match.group(2) or '').strip()

        if single_expr:
            single_module = unwrap_return_module(single_expr)
            if not single_module:
                self.error(text, 'single module export is incorrectly defined')
            return ReturnDefinition(default_name, 'single', single_module=single_module)
        else:
            tablestr: str = match.group(1)
            if not tablestr:
                self.error(text, 'module export is incorrectly defined')

            try:
                dict_data = self._get_dict_data(tablestr)
            except LuaParserError:
                return ReturnDefinition(default_name, 'single', single_module=RETURN_TABLE_MODULE_NAME)

            if dict_data:
                if any(not unwrap_return_module(v) and not is_literal_function(v) for v in dict_data.values()):
                    return ReturnDefinition(default_name, 'single', single_module=RETURN_TABLE_MODULE_NAME)

                return ReturnDefinition(
                    default_name,
                    'dict',
                    dict_val={self._map_dict_return(k, v): k for k, v in dict_data.items()},
                )
            else:
                self.error(text, 'module export is not a table')

    def _get_returned_value(self, text: str, returned: ReturnDefinition):
        if text.lstrip().startswith('return') and returned.single_module == RETURN_TABLE_MODULE_NAME:
            return ReturnedValue(self.file, self.file_name, self.file_name)

        match = VARIABLE_REGEX.search(text)
        if not match:
            self.error(text, 'code block is not a variable declaration')

        name: str = match.group(1)
        returned_name, is_submodule = returned.get_returned_name(name)

        if not (name and returned_name):
            self.error(text, 'invalid returned value definition or it is not exported.')

        return ReturnedValue(self.file, name, returned_name, is_submodule)

    def _build_param_dict(self, raw_params: str):
        if raw_params.strip() == '':
            return {}
        return map_param_list(split_top_level_csv(raw_params))

    def _normalize_non_strict_param_dict(self, param_dict: dict[str, str]):
        has_function_typed_param = any('->' in value for value in param_dict.values())
        if has_function_typed_param:
            return param_dict

        for idx, key in enumerate(param_dict):
            if idx > 0 and param_dict[key] == 'number':
                param_dict[key] = 'string'

        return param_dict

    def _get_dict_return_alias_method(self, text: str, modules: dict[str, LuaModule], returned: ReturnDefinition):
        if returned.type != 'dict':
            return None

        entry = RETURN_TABLE_ENTRY_REGEX.search(text)
        if not entry:
            return None

        module_name = unwrap_return_module(entry.group(2).strip())
        if not module_name:
            return None

        returned_name, is_submodule = returned.get_returned_name(module_name)
        if not (returned_name and is_submodule):
            return None

        module = self._get_return_table_module(modules)
        return LuaMethod(returned_name, module, {})

    def _next_method_name(self, method_name: str):
        match = re.match(r'^(.*?)(\d+)$', method_name)
        if match:
            base = match.group(1)
            index = int(match.group(2)) + 1
            return f'{base}{index}'
        return f'{method_name}2'

    def _resolve_method_name_collision(self, method: LuaMethod):
        module_methods = method.module.methods
        name = method.name

        if name not in module_methods:
            return name

        existing = module_methods[name]
        if existing.call_type == method.call_type:
            return name

        candidate = self._next_method_name(name)
        while candidate in module_methods:
            candidate = self._next_method_name(candidate)
        return candidate

    def _track_method(self, method: LuaMethod):
        module_name = method.module.name
        is_implicit = method.call_type == ''

        if not is_implicit:
            self.explicit_method_modules.add(module_name)
            implicit_names = self.implicit_method_names.pop(module_name, set())
            for name in implicit_names:
                method.module.methods.pop(name, None)

        if is_implicit and module_name in self.explicit_method_modules:
            return

        method.name = self._resolve_method_name_collision(method)
        method.module.methods[method.name] = method

        if is_implicit:
            self.implicit_method_names.setdefault(module_name, set()).add(method.name)

    def _get_function(
        self,
        text: str,
        modules: dict[str, LuaModule],
        returned: ReturnDefinition,
        strict: bool = True,
    ):
        if not strict and not is_function_definition(text):
            return None

        parsed = parse_function_signature(text)
        if not parsed:
            alias_method = self._get_dict_return_alias_method(text, modules, returned)
            if alias_method:
                return alias_method

            if strict:
                self.error(text, 'function is incorrectly defined')
            return None

        module_name, fun_name, call_type, raw_params, return_type = parsed

        if fun_name == '':
            self.error(text, 'method is incorrectly defined')

        param_dict = self._build_param_dict(raw_params)

        if not strict:
            # Keep inferred method typing behavior consistent for module method indexes.
            param_dict = self._normalize_non_strict_param_dict(param_dict)

        if module_name is not None:
            if module_name not in modules:
                if strict:
                    self.error(module_name, 'cannot use method annotations for an unindexed module.')
                return None
            return LuaMethod(fun_name, modules[module_name], param_dict, return_type, call_type)

        if returned.type == 'single':
            entry = RETURN_TABLE_ENTRY_REGEX.search(text)
            if entry and entry.group(2).strip().startswith('function'):
                module = modules.get(returned.single_module or '') or self._get_return_table_module(modules)
                return LuaMethod(fun_name, module, param_dict, return_type, call_type)

            module = modules.get(returned.single_module or '')
            if module:
                return LuaMethod(fun_name, module, param_dict, return_type, call_type)

            returned_name, is_submodule = returned.get_returned_name(fun_name)
            if strict and returned_name and not is_submodule:
                module = LuaModule(self.file, fun_name, returned_name)
                return LuaMethod(fun_name, module, param_dict, return_type, call_type, direct_return=True)

        # Allow `function foo()` to be a method annotation target when `foo`
        # is exported from a literal return table: `return { alias = foo }`.
        returned_name, is_submodule = returned.get_returned_name(fun_name)
        if returned.type != 'dict' or not (returned_name and is_submodule):
            if strict:
                self.error(fun_name, 'cannot use method annotations for an unindexed module.')
            return None
        assert returned_name is not None

        module = self._get_return_table_module(modules)
        return LuaMethod(returned_name, module, param_dict, return_type, call_type)

    def _get_return_table_module(self, modules: dict[str, LuaModule]):
        module = modules.get(RETURN_TABLE_MODULE_NAME)
        if module is None:
            module = LuaModule(self.file, RETURN_TABLE_MODULE_NAME, self.file_name, False)
            modules[module.name] = module
        return module

    # main functions
    def error(self, text: str, message: str):
        raise LuaParserError(message, text, self.cur_line, self.file_name)

    def parse(self, text: str):
        returned = self._get_returned(text, self.file_name)
        if not returned:
            logger().warn(f'Skipping file {self.file_name}; doesn\'t return a value')
            return
        lines = [l.rstrip() for l in text.splitlines()]

        for i, line in enumerate(lines):
            self.cur_line += 1
            lstrip = line.lstrip()
            # skip empty lines
            if line == '':
                continue

            # comments
            elif lstrip.startswith('--'):
                # annotation
                if lstrip.startswith(ANNOTATION_PREFIX):
                    anot = self._parse_annotation(lstrip, self.reg)
                    if anot:
                        self.cur_annotations.append(anot)
                    else:
                        self.error(line, 'Not an annotation')

            else:
                code_line = line.split('--')[0].rstrip()
                code_line = _collect_multiline_function_signature(code_line, lines, i)
                # Track methods defined in code regardless of annotation usage.
                method = self._get_function(code_line, self.modules, returned, strict=False)
                if method is not None:
                    self._track_method(method)

                # if there are annotations in this block of code, then find adornee
                if len(self.cur_annotations) > 0:
                    adefs = [anot.adef for anot in self.cur_annotations]

                    self._check_anot_relations(line, adefs)
                    self._check_anot_scopes(line, adefs)

                    scope = adefs[0].scope

                    # strip comments
                    line = code_line

                    # methods
                    if scope == 'method':
                        line = _collect_multiline_function_signature(line, lines, i)
                        method = self._get_function(line, self.modules, returned)
                        assert method
                        set_adornee(self.cur_annotations, method)

                    # module
                    elif scope == 'module':
                        match = MODULE_REGEX.search(line)
                        if match:
                            name: str = match.group(1)
                            returned_name, is_submodule = returned.get_returned_name(name)
                        else:
                            entry = RETURN_TABLE_ENTRY_REGEX.search(line)
                            if not entry:
                                self.error(line, 'code block is not a module')
                            name = unwrap_return_module(entry.group(2).strip()) or ''
                            returned_name, is_submodule = returned.get_returned_name(name)

                        if not (name and returned_name):
                            self.error(line, 'invalid module definition or it is not returned.')

                        module = LuaModule(self.file, name, returned_name, is_submodule)
                        set_adornee(self.cur_annotations, module)
                        self.modules[module.name] = module

                    # returned value
                    elif scope == 'returned_value':
                        returned_value = self._get_returned_value(line, returned)
                        set_adornee(self.cur_annotations, returned_value)

                    # type
                    elif scope == 'type':
                        # get entire code block
                        block = ''
                        for line2 in lines[i:]:
                            block += line2 + '\n'
                            if '}' in line2:
                                break

                        # use type regex
                        match = TYPE_REGEX.search(block)
                        if not match:
                            self.error(line, 'code block is not a type definition')

                        exported = bool(match.group(1))
                        name: str = match.group(2)
                        contents: str = match.group(3)

                        if not (name and contents):
                            self.error(line, 'type definition is missing name or contents')

                        if contents.startswith('{'):
                            data = self._get_dict_data(contents)
                        else:
                            data = contents

                        if not data:
                            self.error(line, 'type definition is missing type data')

                        lua_type = LuaType(name, data, exported)

                        set_adornee(self.cur_annotations, lua_type)
                        self.types[name] = lua_type

                    # now run anot on_build
                    for anot in self.cur_annotations:
                        adef = anot.adef
                        for on_build in (
                            adef.on_build,
                            adef.extends.on_build if adef.extends else None,
                        ):
                            if not on_build:
                                continue
                            on_build(AnnotationBuildCtx(anot, self, self.build_ctx))

                    self.annotations += self.cur_annotations
                    self.cur_annotations = []
