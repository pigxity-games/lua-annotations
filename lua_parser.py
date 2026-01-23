from dataclasses import dataclass
from typing import Optional, TypedDict

from annotations import scope

class TypedVar(TypedDict):
    name: str
    type: str

@dataclass
class LuaMethod():
    name: str
    module: str
    args: Optional[list[TypedVar]]
    returnType: Optional[str]

def parse_block(lines: list[str], scope: scope):
    for line in lines:
        if scope == 'method':
            