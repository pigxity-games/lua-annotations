from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Literal, Optional

from api.annotations import AnnotationDef
from exceptions import ParseError

if TYPE_CHECKING:
    from api.lua_dict import LuaPathResolver

ANNOTATION_PREFIX = '--@'
ARG_SEP = ','

#matches module/type name for module/type declarations
MODULE_REGEX = re.compile(r'^local\s+(\w+)\s*=.*\{')

#matches keys (group 1) and values (group 2) in a dictonary seperated by = or :
DICT_REGEX = re.compile(r'(\w+)\s*[:=]\s*(.*?)(?:,\s*|$)', re.MULTILINE)

#group 1 = module name, group 2 = function name, group 3 = parameters, group 4 = return type
#use dict_regex for group 2 matches
FUNCTION_REGEX = re.compile(r'^\s*(?:function\s+)?(?:(\w+)[.:])?(\w+)\s*(?:=\s*function\s*)?\(\s*([^)]*)\s*\)\s*(?::\s([^\s]+))?')

#group 2 if single return, group 1 if table returned (use dict_regex)
RETURN_REGEX = re.compile(r'return\s*\{([\s\S]*?)\}\s*$|^return\s(\w*)', re.MULTILINE)

#group 1 exists if exported, group 2 = name, group 3 = contents
TYPE_REGEX = re.compile(r'^\s*(export\b)?\s*type\s+(\w+)\s*=\s*(\{[\s\S]*?\}|[^\n]+)\s*\s*$', re.MULTILINE)

#splits annotation arguments while ignoring ones inside brackets
ANNOTATION_ARG_RE = re.compile(r',\s*(?![^\[]*\])')

type Adornee = LuaModule | LuaMethod | LuaType


@dataclass
class LuaMethod():
    name: str
    module: LuaModule
    params: dict[str, str] = field(default_factory=dict)
    return_type: Optional[str] = None

    def get_path(self, relative: bool=False, require: bool=False, sep: str='.'):
        return self.module.get_path(relative, require, sep + self.name)


@dataclass
class LuaModule():
    file: Path
    name: str
    returned_name: str
    submodule: bool=False


    def get_path(self, relative: bool=False, require: bool=False, ext: Optional[str]=None):
        """Similar to the LuaPath constructor, but it takes the module's submodule status into account."""
        from api.lua_dict import LuaPath

        if self.submodule:
            return LuaPath(self.file, relative, require, self.returned_name, ext)
        else:
            return LuaPath(self.file, relative, require, ext=ext)


    def get_expr(self, resolver: LuaPathResolver, relative: bool=False):
        path = self.get_path(relative, True)
        return f'local {self.returned_name} = {path.to_lua(resolver)}'


@dataclass
class LuaType():
    name: str
    data: dict[str, str] | str
    exported: bool=False


@dataclass
class Annotation():
    adef: AnnotationDef
    name: str
    args_val: list[Any]
    kwargs_val: dict[str, Any]
    adornee: Adornee = field(init=False)

    def asdict(self):
        return {
            'name': self.name,
            'args': self.args_val,
            'kwargs': self.kwargs_val,
            'adornee': self.adornee.get_path(require=True)
        }


@dataclass
class ReturnedValue():
    default_name: str
    type: Literal['single', 'dict']
    single_module: Optional[str] = None
    dict_val: Optional[dict[str, str]] = None

    def get_returned_name(self, module: str):
        if self.type == 'single':
            if self.single_module == module:
                return self.default_name, False
        elif self.type == 'dict':
            if self.dict_val:
                return self.dict_val.get(module), True

        return None, False


@dataclass
class LuaParserError(ParseError):
    """Raised for invalid text when parsing lua files"""
    message: str
    text: str
    line_num: int
    file_name: str

    def __post_init__(self):
        super().__init__(f'Error on line `{self.line_num}` in file `{self.file_name}.lua` : {self.message}\n{self.text}')