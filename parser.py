from dataclasses import dataclass
import re
from typing import Any, Optional

from annotations import AnnotationDef, ExtensionContext, scope
from default_extension import main as default_extension

ANNOTATION_PREFIX = '--@'
ARG_SEP = ', '

#matches module/type name for module/type declarations
TYPE_LINE_REGEX = re.compile('^type\s+(\w+)')
MODULE_REGEX = re.compile('^local\s+(\w+)\s*=.*\{')

#matches keys (group 1) and values (group 2) in a dictonary seperated by = or :
DICT_REGEX = re.compile('(\w+)\s*[:=]\s*(.*?)(?:,\s*|$)')

#group 1 = module name, group 2 = function name, group 3 = parameters, group 4 = return type
#use dict_regex for group 2 matches
FUNCTION_REGEX = re.compile('^\s*(?:function\s+)?(?:(\w+)[.:])?(\w+)\s*(?:=\s*function\s*)?\(\s*([^)]*)\s*\)\s*(?::\s([^\s]+))?')

#group 2 if single return, group 1 if table returned (use dict_regex)
RETURN_REGEX = re.compile('return\s*\{([\s\S]*?)\}\s*$|^return\s(\w*)')

type adornee = LuaModule | LuaMethod

@dataclass
class TypedValue():
    type: str
    name: str

@dataclass
class LuaMethod():
    pass

@dataclass
class LuaModule():
    name: str
    returned_name: str

@dataclass
class Annotation():
    adef: AnnotationDef
    name: str
    args_val: list[Any]
    kwargs_val: dict[str, Any]
    adornee: Optional[adornee]=None

def set_adornee(anots: list[Annotation], adornee: adornee):
    for anot in anots:
        anot.adornee = adornee

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
            args_val[i] = proc(arg)

    return args_val, kwargs_val

def parse_annotation(text: str, ctx: ExtensionContext):
    parts = text.removeprefix(ANNOTATION_PREFIX).split(ARG_SEP)
    name = parts[0]

    adef = ctx.registry[name]
    args, kwargs = parse_anot_args(adef, parts[1:-1])

    return Annotation(adef, name, args, kwargs)

def parse_lines(lines: list[str], ctx: ExtensionContext):
    annotations: list[Annotation] = []
    cur_annotations: list[Annotation] = []
    
    for line in lines:
        #skip empty lines
        if line == '':
            continue
       
        #comments
        elif line.startswith('--'):
            #annotation
            if line.startswith(ANNOTATION_PREFIX):
                cur_annotations.append(parse_annotation(line, ctx))

        else:
            #if there are annotations in this block of code, then find adornee
            if len(cur_annotations) > 0:
                adefs = [anot.adef for anot in cur_annotations]
                assert(annotations_scopes_equal(adefs))
                assert(annotations_are_mutual(adefs))
                scope = adefs[0].scope

                #strip comments
                line = line.split('--')[0]
                
                #methods
                if scope == 'method':
                    pass

                #modul
                elif scope == 'module':
                    match = MODULE_REGEX.match(line)
                    assert(match)
                    
                    name = match.group(1)
                    set_adornee(cur_annotations, LuaModule(name))

                annotations += cur_annotations
                cur_annotations = []

#Test
if __name__ == 'main':
    ctx = ExtensionContext()
    default_extension.load(ctx)
    
    with open('test/Test.lua', 'r') as f:
        parse_lines([l.rstrip() for l in f.readlines()], ctx)