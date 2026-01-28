from dataclasses import dataclass, field
from typing import Any

from annotations import AnnotationDef, AnnotationRegistry
from default_extension import main as default_extension
from parser_schemas import *

#assertion functions
def annotations_scopes_equal(anots: list[AnnotationDef]):
    scope = anots[0].scope
    for anot in anots:
        if not anot.scope == scope:
            return False
    return True

def annotations_are_mutual(anots: list[AnnotationDef]):
    #TODO
    return True

#parsing
def set_adornee(anots: list[Annotation], adornee: Adornee):
    for anot in anots:
        anot.adornee = adornee

def parse_anot_args(adef: AnnotationDef, args: list[str]):
    kwargs_val: dict[str, Any] = {}
    args_val: list[Any] = []

    for i, arg in enumerate(args):
        if '=' in arg:
            name, val = arg.split('=')
            proc = adef.kwargs[name]
            kwargs_val[name] = proc(val)
        else:
            proc = adef.args[i]
            args_val.append(proc(arg))

    return args_val, kwargs_val

def parse_annotation(text: str, ctx: AnnotationRegistry):
    parts = remove_whitespace(ANNOTATION_ARG_RE.split(text.removeprefix(ANNOTATION_PREFIX)))
    name = parts[0]

    adef = ctx.registry.get(name)
    if not adef:
        return

    args, kwargs = parse_anot_args(adef, parts[1:])

    return Annotation(adef, name, args, kwargs)

def get_dict_data(text: str):
    matches = DICT_REGEX.findall(text)
    assert len(matches) > 0

    keys: list[str] = [m[0] for m in matches]
    values: list[str] = [m[1] for m in matches]
        
    if len(keys) == len(values):
        out: dict[str, str] = {}
        for i, key in enumerate(keys):
            out[key] = values[i]

        return out

def reverse_dict(d: dict[Any, Any]):
    return {v: k for k, v in d.items()}

def get_returned(text: str, default_name: str):
    match = RETURN_REGEX.search(text)
    if not match:
        return

    single: str = match.group(2)

    if single:
        return ReturnedValue(default_name, 'single', single_module=single)
    else:
        tablestr: str = match.group(1)
        assert tablestr
        dict_data = get_dict_data(tablestr)
        assert dict_data
        return ReturnedValue(default_name, 'dict', dict=reverse_dict(dict_data))

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


def get_function(text: str, modules: dict[str, LuaModule]):
    match = FUNCTION_REGEX.search(text)
    assert match

    module_name: str = match.group(1)
    fun_name: str = match.group(2)
    raw_params: str = match.group(3)
    return_type: str = match.group(4) or 'any'

    assert module_name and fun_name
    if not raw_params.strip() == '':
        params = remove_whitespace(raw_params.split(','))
        param_dict = map_param_list(params)
    else:
        param_dict = {}

    return LuaMethod(fun_name, modules[module_name], param_dict, return_type)

@dataclass
class FileParser():
    reg: AnnotationRegistry
    file_name: str
    annotations: list[Annotation] = field(default_factory=list)
    cur_annotations: list[Annotation] = field(default_factory=list)
    modules: dict[str, LuaModule] = field(default_factory=dict)

    def parse(self, text: str):        
        returned = get_returned(text, self.file_name)
        if not returned:
            print(f'Skipping file {self.file_name}; doesn\'t return a value')
            return
        lines = [l.rstrip() for l in text.splitlines()]

        for line in lines:
            #skip empty lines
            if line == '':
                continue
        
            #comments
            elif line.startswith('--'):
                #annotation
                if line.startswith(ANNOTATION_PREFIX):
                    anot = parse_annotation(line, self.reg)
                    if anot:
                        self.cur_annotations.append(anot)
                    else:
                        print(f'Not an annotation: `{line}`')

            else:
                #if there are annotations in this block of code, then find adornee
                if len(self.cur_annotations) > 0:
                    adefs = [anot.adef for anot in self.cur_annotations]
                    assert annotations_scopes_equal(adefs)
                    assert annotations_are_mutual(adefs)
                    scope = adefs[0].scope

                    #strip comments
                    line = line.split('--')[0]
                    
                    #methods
                    if scope == 'method':
                        method = get_function(line, self.modules)
                        set_adornee(self.cur_annotations, method)

                    #module
                    elif scope == 'module':
                        match = MODULE_REGEX.search(line)
                        assert match
                        
                        name: str = match.group(1)
                        returned_name = returned.get_returned_name(name)
                        assert name and returned_name
                
                        module = LuaModule(name, returned_name)
                        set_adornee(self.cur_annotations, module)
                        self.modules[module.name] = module

                    #type
                    elif scope == 'type':
                        pass

                    self.annotations += self.cur_annotations
                    self.cur_annotations = []

#Test
if __name__ == '__main__':
    ctx = AnnotationRegistry()
    default_extension.load(ctx)
    
    with open('./test/Test.lua', 'r') as f:
        parser = FileParser(ctx, 'Test')
        parser.parse(f.read())

    for module in parser.modules.values():
        print(module.name, module.returned_name)

    for anot in parser.annotations:
        print(anot.name, anot.adornee, anot.args_val, anot.kwargs_val)