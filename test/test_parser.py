from pathlib import Path

import pytest

from lua_annotations.api.annotations import AnnotationDef, SortedRegistry
from lua_annotations.api.lua_dict import LuaPathResolver
from lua_annotations.parser import FileParser
from lua_annotations.parser_schemas import (
    LuaMethod,
    LuaModule,
    LuaParserError,
    LuaType,
    ReturnedValue,
)


def make_registry() -> SortedRegistry:
    annotations = {
        "moduleAnn": AnnotationDef("moduleAnn", scope="module"),
        "methodAnn": AnnotationDef(
            "methodAnn",
            scope="method",
            args=[str],
            kwargs={"flag": str},
        ),
        "typeAnn": AnnotationDef("typeAnn", scope="type"),
        "valueAnn": AnnotationDef("valueAnn", scope="returned_value"),
    }
    return SortedRegistry([], [], annotations)


def parse_text(tmp_path: Path, filename: str, text: str) -> FileParser:
    file = tmp_path / filename
    parser = FileParser(make_registry(), file, None)  # pyright: ignore[reportArgumentType]
    parser.parse(text)
    return parser


def test_parser_builds_lua_module_and_lua_methods_with_state(tmp_path: Path):
    parser = parse_text(
        tmp_path,
        "SingleReturn.lua",
        """--@moduleAnn
local Root = {}

--@methodAnn, hello, flag=world
function Root.run(count: number, name): string
end

--@methodAnn
function Root:reset()
end

return Root
""",
    )

    module = parser.modules["Root"]
    assert isinstance(module, LuaModule)
    assert module.returned_name == "SingleReturn"
    assert module.submodule is False

    method_anots = [a for a in parser.annotations if a.name == "methodAnn"]
    assert len(method_anots) == 2
    assert all(isinstance(a.adornee, LuaMethod) for a in method_anots)

    run_method = next(a.adornee for a in method_anots if a.adornee.name == "run")
    assert isinstance(run_method, LuaMethod)
    assert run_method.params == {"count": "number", "name": "any"}
    assert run_method.return_type == "string"

    reset_method = next(a.adornee for a in method_anots if a.adornee.name == "reset")
    assert isinstance(reset_method, LuaMethod)
    assert reset_method.params == {}
    assert reset_method.return_type == "any"


def test_parser_builds_submodule_and_returned_value_states(tmp_path: Path):
    parser = parse_text(
        tmp_path,
        "Submodule.lua",
        """--@moduleAnn
local Mod = {}

--@valueAnn
local RawValue = 42

return {
    ExportedMod = Mod,
    ExportedValue = RawValue
}
""",
    )

    module = parser.modules["Mod"]
    assert isinstance(module, LuaModule)
    assert module.submodule is True
    assert module.returned_name == "ExportedMod"
    assert module.get_path(require=True).properties == ["ExportedMod"]

    value_anot = next(a for a in parser.annotations if a.name == "valueAnn")
    assert isinstance(value_anot.adornee, ReturnedValue)
    assert value_anot.adornee.submodule is True
    assert value_anot.adornee.returned_name == "ExportedValue"
    assert value_anot.adornee.get_path(require=True).properties == ["ExportedValue"]

    resolver = LuaPathResolver(
        {
            "server": {tmp_path: ":Project"},
            "client": {},
            "shared": {},
        }
    )
    assert (
        module.get_expr(resolver)
        == "local ExportedMod = require(ServerScriptService.Project.Submodule).ExportedMod"
    )


def test_parser_builds_luatype_exported_and_unexported_states(tmp_path: Path):
    parser = parse_text(
        tmp_path,
        "Types.lua",
        """--@typeAnn
export type PublicType = {
    id: number,
    name: string,
}

--@typeAnn
type InternalType = PublicType | string

local Root = {}
return Root
""",
    )

    public_type = parser.types["PublicType"]
    assert isinstance(public_type, LuaType)
    assert public_type.exported is True
    assert public_type.data == {"id": "number", "name": "string"}

    internal_type = parser.types["InternalType"]
    assert isinstance(internal_type, LuaType)
    assert internal_type.exported is False
    assert internal_type.data == "PublicType | string"

    type_anots = [a for a in parser.annotations if a.name == "typeAnn"]
    assert len(type_anots) == 2
    assert all(isinstance(a.adornee, LuaType) for a in type_anots)


def test_parser_raises_luaparsererror_for_unindexed_method_module(tmp_path: Path):
    with pytest.raises(LuaParserError) as exc_info:
        parse_text(
            tmp_path,
            "Broken.lua",
            """--@methodAnn
function Missing.run()
end

return Missing
""",
        )

    err = exc_info.value
    assert err.file_name == "Broken"
    assert err.line_num == 2
    assert "cannot use method annotations for an unindexed module" in str(err)
