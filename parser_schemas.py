from dataclasses import dataclass, field
import re
from typing import Any, Literal, Optional

from annotations import AnnotationDef


ANNOTATION_PREFIX = '--@'
ARG_SEP = ','

#matches module/type name for module/type declarations
TYPE_LINE_REGEX = re.compile(r'^type\s+(\w+)')
MODULE_REGEX = re.compile(r'^local\s+(\w+)\s*=.*\{')

#matches keys (group 1) and values (group 2) in a dictonary seperated by = or :
DICT_REGEX = re.compile(r'(\w+)\s*[:=]\s*(.*?)(?:,\s*|$)', re.MULTILINE)

#group 1 = module name, group 2 = function name, group 3 = parameters, group 4 = return type
#use dict_regex for group 2 matches
FUNCTION_REGEX = re.compile(r'^\s*(?:function\s+)?(?:(\w+)[.:])?(\w+)\s*(?:=\s*function\s*)?\(\s*([^)]*)\s*\)\s*(?::\s([^\s]+))?')

#group 2 if single return, group 1 if table returned (use dict_regex)
RETURN_REGEX = re.compile(r'return\s*\{([\s\S]*?)\}\s*$|^return\s(\w*)', re.MULTILINE)

#splits annotation arguments while ignoring ones inside brackets
ANNOTATION_ARG_RE = re.compile(r',\s*(?![^\[]*\])')

type Adornee = LuaModule | LuaMethod

@dataclass
class LuaMethod():
    name: str
    module: LuaModule
    params: dict[str, str] = field(default_factory=dict)
    return_type: Optional[str] = None

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
    adornee: Adornee = field(init=False)


@dataclass
class ReturnedValue():
    default_name: str
    type: Literal['single', 'dict']
    single_module: Optional[str] = None
    dict: Optional[dict[str, str]] = None

    def get_returned_name(self, module: str):
        if self.type == 'single':
            if self.single_module == module:
                return self.default_name
        elif self.type == 'dict':
            if self.dict:
                return self.dict.get(module)

@dataclass
class ParserException(Exception):
    message: str
    text: str
    line_num: int
    file_name: str

    def __post_init__(self):
        super().__init__(f'Error on line `{self.line_num}` in file `{self.file_name}.lua` : {self.message}\n{self.text}')