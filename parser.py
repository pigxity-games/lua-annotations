from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from annotations import AnnotationBuildCtx, AnnotationDef, AnnotationRegistry
from default_extension import main as default_extension
from parser_schemas import *

if TYPE_CHECKING:
    from build_process import BuildProcessCtx

#helper functions
def reverse_dict(d: dict[Any, Any]):
    return {v: k for k, v in d.items()}

def set_adornee(anots: list[Annotation], adornee: Adornee):
    for anot in anots:
        anot.adornee = adornee

def remove_whitespace(t: list[Any]):
    return [p.strip() for p in t]

def map_param_list(params: list[str]):    
    out: dict[str, str] = {}
    for param in params:
        parts = remove_whitespace(param.split(':'))
        if len(parts) > 1:
            out[parts[0]] = parts[1]
        else:
            out[parts[0]] = 'any'

    return out

#parsing
@dataclass
class FileParser():
    reg: AnnotationRegistry
    file: Path
    build_ctx: 'BuildProcessCtx'
    annotations: list[Annotation] = field(default_factory=list)
    cur_annotations: list[Annotation] = field(default_factory=list)
    modules: dict[str, LuaModule] = field(default_factory=dict)
    types: dict[str, LuaType] = field(default_factory=dict)
    cur_line = 0

    def __post_init__(self):
        self.file_name = self.file.name.split('.')[0]

    #assertion functions
    def _check_anot_scopes(self, line: str, anots: list[AnnotationDef]):
        scope = anots[0].scope
        for anot in anots:
            if not anot.scope == scope:
                self.error(line, f'all annotations must have scope: `{scope}`')

    def _check_anot_relations(self, line: str, anots: list[AnnotationDef]):
        for anot in anots:
            for inc in anot.mutual_exclude:
                if inc in anots:
                    self.error(line, f'annotation {anot.name} excludes {inc.name}, but it is present in this code block')

            for inc in anot.mutual_include:
                if not inc in anots:
                    self.error(line, f'annotation {anot.name} requires {inc.name}, but it is not present in this code block')


    #parsing helpers
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

    def _parse_annotation(self, text: str, ctx: AnnotationRegistry):
        parts = remove_whitespace(ANNOTATION_ARG_RE.split(text.removeprefix(ANNOTATION_PREFIX)))
        name = parts[0]

        adef = ctx.registry.get(name)
        if adef:
            args, kwargs = self._parse_anot_args(adef, parts[1:])
            return Annotation(adef, name, args, kwargs)
        else:
            self.error(text, 'Annotation does not exist')

    def _get_dict_data(self, text: str):
        matches = DICT_REGEX.findall(text)
        if not len(matches) > 0:
            self.error(text, 'line is not a dict')

        keys: list[str] = [m[0] for m in matches]
        values: list[str] = [m[1] for m in matches]
            
        if len(keys) == len(values):
            out: dict[str, str] = {}
            for i, key in enumerate(keys):
                out[key] = values[i].strip().removesuffix('}').strip()

            return out

    def _get_returned(self, text: str, default_name: str):
        match = RETURN_REGEX.search(text)
        if not match:
            return

        single: str = match.group(2)

        if single:
            return ReturnedValue(default_name, 'single', single_module=single)
        else:
            tablestr: str = match.group(1)
            if not tablestr:
                self.error(text, 'module export is incorrectly defined')

            dict_data = self._get_dict_data(tablestr)
            if dict_data:
                return ReturnedValue(default_name, 'dict', dict_val=reverse_dict(dict_data))
            else:
                self.error(text, 'module export is not a table')

    def _get_function(self, text: str, modules: dict[str, LuaModule]):
        match = FUNCTION_REGEX.search(text)
        if not match:
            self.error(text, 'function is incorrectly defined')

        module_name: str = match.group(1)
        fun_name: str = match.group(2)
        raw_params: str = match.group(3)
        return_type: str = match.group(4) or 'any'

        if not (module_name or fun_name):
            self.error(text, 'method is incorrectly defined')

        if not raw_params.strip() == '':
            params = remove_whitespace(raw_params.split(','))
            param_dict = map_param_list(params)
        else:
            param_dict = {}

        if not module_name in modules:
            self.error(module_name, 'cannot use method annotations for an unindexed module.')
        return LuaMethod(fun_name, modules[module_name], param_dict, return_type)


    #main functions
    def error(self, text: str, message: str):
        raise ParserException(text, message, self.cur_line, self.file_name)

    def parse(self, text: str):        
        returned = self._get_returned(text, self.file_name)
        if not returned:
            print(f'Skipping file {self.file_name}; doesn\'t return a value')
            return
        lines = [l.rstrip() for l in text.splitlines()]

        for i, line in enumerate(lines):
            self.cur_line += 1
            #skip empty lines
            if line == '':
                continue
        
            #comments
            elif line.startswith('--'):
                #annotation
                if line.startswith(ANNOTATION_PREFIX):
                    anot = self._parse_annotation(line, self.reg)
                    if anot:
                        self.cur_annotations.append(anot)
                    else:
                        self.error(line, 'Not an annotation')

            else:
                #if there are annotations in this block of code, then find adornee
                if len(self.cur_annotations) > 0:
                    adefs = [anot.adef for anot in self.cur_annotations]

                    self._check_anot_relations(line, adefs)
                    self._check_anot_scopes(line, adefs)

                    scope = adefs[0].scope

                    #strip comments
                    line = line.split('--')[0]
                    
                    #methods
                    if scope == 'method':
                        method = self._get_function(line, self.modules)
                        set_adornee(self.cur_annotations, method)

                    #module
                    elif scope == 'module':
                        match = MODULE_REGEX.search(line)
                        if not match:
                            self.error(line, 'code block is not a module')
                        
                        name: str = match.group(1)
                        returned_name = returned.get_returned_name(name)

                        if not (name and returned_name):
                            self.error(line, 'invalid module definition or it is not returned.')

                        module = LuaModule(name, returned_name)
                        set_adornee(self.cur_annotations, module)
                        self.modules[module.name] = module

                    #type
                    elif scope == 'type':
                        #get entire code block
                        block = ''
                        for line2 in lines[i:]:
                            block += line2 + '\n'
                            if '}' in line2:
                                break

                        #use type regex
                        match = TYPE_REGEX.search(block)
                        if not match:
                            self.error(line, 'code block is not a type definition')

                        exported = bool(match.group(1))
                        name: str = match.group(2)
                        contents: str = match.group(3)

                        assert name and contents

                        if contents.startswith('{'):
                            data = self._get_dict_data(contents)
                        else:
                            data = contents

                        assert data

                        lua_type = LuaType(name, data, exported)

                        set_adornee(self.cur_annotations, lua_type)
                        self.types[name] = lua_type

                    #now run anot on_build
                    for anot in self.cur_annotations:
                        if anot.adef.on_build:
                            anot.adef.on_build(AnnotationBuildCtx(anot, self, self.build_ctx))

                    self.annotations += self.cur_annotations
                    self.cur_annotations = []

#Test
if __name__ == '__main__':
    ctx = AnnotationRegistry()
    default_extension.load(ctx)
    
    test_file = Path('./test/Test.lua')
    with test_file.open('r') as f:
        parser = FileParser(ctx, test_file, None)  # pyright: ignore[reportArgumentType]
        parser.parse(f.read())

    for module in parser.modules.values():
        print(module.name, module.returned_name)

    for anot in parser.annotations:
        print(anot.name, anot.adornee, anot.args_val, anot.kwargs_val)