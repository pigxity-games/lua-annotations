from pathlib import Path, PurePath

import pytest  # pyright: ignore[reportMissingImports]

from lua_annotations.api.annotations import SortedRegistry
from lua_annotations.api.lua_dict import (
    LuaExpr,
    LuaPath,
    convert_dict,
    convert_dict_module,
    convert_dict_type,
)
from lua_annotations.build_process import ProcessCtx
from lua_annotations.exceptions import BuildError

from helpers import make_resolver, make_workspace


def test_luapath_resolves_workspace_paths_and_tracks_imports(tmp_path: Path):
    resolver = make_resolver(tmp_path)

    path = LuaPath(tmp_path / "server" / "Services" / "Data.lua", require=True)
    assert path.to_lua(resolver) == "require(ServerScriptService.ServerRoot.Services.Data)"
    assert resolver.get_import_lines() == ['local ServerScriptService = game:GetService("ServerScriptService")']


def test_luapath_resolves_env_prefixed_paths(tmp_path: Path):
    resolver = make_resolver(tmp_path)
    path = LuaPath(PurePath("shared/Util/Math.lua"), require=True)

    assert path.to_lua(resolver) == "require(ReplicatedStorage.Util.Math)"
    assert resolver.get_import_lines() == ['local ReplicatedStorage = game:GetService("ReplicatedStorage")']


def test_luapath_relative_and_function_wrapping_behavior():
    relative = LuaPath(PurePath("Some/Module.lua"), relative=True)
    assert relative.to_lua_relative() == "script.Parent.Some.Module"

    with_props = LuaPath(PurePath("Some/Module.lua"), relative=True, properties=["call"])
    assert with_props.to_lua_relative() == "function() return require(script.Parent.Some.Module).call end"

    as_function = LuaPath(PurePath("Some/Module.lua"), relative=True, function=True)
    assert as_function.to_lua_relative() == "function() return script.Parent.Some.Module end"


def test_luapath_inline_require_uses_service_expr_without_imports(tmp_path: Path):
    resolver = make_resolver(tmp_path)
    path = LuaPath(tmp_path / "server" / "Pkg" / "Remote.lua", require=True)

    assert path.to_lua(resolver, inline_require=True) == 'require(game:GetService("ServerScriptService").ServerRoot.Pkg.Remote)'
    assert resolver.get_import_lines() == []


def test_luapath_cache_uses_getcached_and_builds_module_paths(tmp_path: Path):
    resolver = make_resolver(tmp_path)
    path = LuaPath(tmp_path / 'server' / 'Services' / 'Data.lua', require=True, cache=True)

    assert path.to_lua(resolver) == 'getCached("Data")'
    assert convert_dict(resolver, resolver.get_cached_module_paths(), prefix='local modulePaths =') == (
        'local ServerScriptService = game:GetService("ServerScriptService")\n'
        '\n'
        'local modulePaths = {\n'
        '    Data = {\n'
        '        path = {ServerScriptService.ServerRoot, "Services", "Data"},\n'
        '    },\n'
        '}\n'
    )


def test_luapath_cache_works_with_function_and_properties(tmp_path: Path):
    resolver = make_resolver(tmp_path)
    path = LuaPath(
        tmp_path / 'server' / 'Pkg' / 'Remote.lua',
        require=True,
        properties=['call'],
        function=True,
        cache=True,
    )

    assert path.to_lua(resolver) == 'function() return getCached("Remote").call end'


def test_luapath_cache_can_resolve_submodule_exports(tmp_path: Path):
    resolver = make_resolver(tmp_path)
    path = LuaPath(
        tmp_path / 'server' / 'Components' / 'CounterComponent.lua',
        require=True,
        properties=['Counter'],
        cache_export='Counter',
        cache=True,
        cache_name='Counter',
    )

    assert path.to_lua(resolver) == 'getCached("Counter")'
    assert convert_dict(resolver, resolver.get_cached_module_paths(), prefix='local modulePaths =') == (
        'local ServerScriptService = game:GetService("ServerScriptService")\n'
        '\n'
        'local modulePaths = {\n'
        '    Counter = {\n'
        '        path = {ServerScriptService.ServerRoot, "Components", "CounterComponent"},\n'
        '        export = "Counter",\n'
        '    },\n'
        '}\n'
    )


def test_luapath_cache_requires_require_true(tmp_path: Path):
    resolver = make_resolver(tmp_path)
    path = LuaPath(tmp_path / 'server' / 'Pkg' / 'Remote.lua', cache=True)

    with pytest.raises(BuildError, match='LuaPath cache requires require=True'):
        path.to_lua(resolver)


def test_luapath_cache_rejects_duplicate_module_names(tmp_path: Path):
    resolver = make_resolver(tmp_path)
    path_a = LuaPath(tmp_path / 'server' / 'PkgA' / 'Remote.lua', require=True, cache=True)
    path_b = LuaPath(tmp_path / 'server' / 'PkgB' / 'Remote.lua', require=True, cache=True)

    assert path_a.to_lua(resolver) == 'getCached("Remote")'
    with pytest.raises(BuildError, match='duplicate module name'):
        path_b.to_lua(resolver)


def test_luapathresolver_raises_for_unknown_path(tmp_path: Path):
    resolver = make_resolver(tmp_path)
    with pytest.raises(ValueError):
        resolver.normalize(PurePath("/outside/project/Test.lua"))


def test_convert_dict_serializes_mixed_values(tmp_path: Path):
    resolver = make_resolver(tmp_path)
    out = convert_dict(
        resolver,
        {
            "name": "demo",
            "live": True,
            "none": None,
            "expr": LuaExpr("game.Workspace"),
            "items": [1, "x"],
            "bad key": 9,
        },
    )

    assert out == (
        'return {\n'
        '    name = "demo",\n'
        "    live = true,\n"
        "    none = nil,\n"
        "    expr = game.Workspace,\n"
        "    items = {\n"
        "        1,\n"
        '        "x",\n'
        "    },\n"
        '    ["bad key"] = 9,\n'
        "}\n"
    )


def test_convert_dict_includes_imports_in_environment_order(tmp_path: Path):
    resolver = make_resolver(tmp_path)
    out = convert_dict(
        resolver,
        {
            "server": LuaPath(tmp_path / "server" / "A.lua", require=True),
            "client": LuaPath(tmp_path / "client" / "B.lua", require=True),
            "shared": LuaPath(tmp_path / "shared" / "C.lua", require=True),
        },
    )

    assert out.startswith(
        'local PlayerScripts = game:GetService("Players").LocalPlayer.PlayerScripts\n'
        'local ServerScriptService = game:GetService("ServerScriptService")\n'
        'local ReplicatedStorage = game:GetService("ReplicatedStorage")\n\n'
        "return {\n"
    )


def test_convert_dict_module_and_type_include_generated_header(tmp_path: Path):
    workspace = make_workspace(tmp_path)
    ctx = ProcessCtx(SortedRegistry([], [], {}), tmp_path, workspace)

    module_out = convert_dict_module(ctx, {"count": 1})
    assert module_out.startswith("-- Generated using lua-anot; do not edit manually.\nreturn {\n")
    assert "count = 1" in module_out

    type_out = convert_dict_type(ctx, {"id": "number"}, "MyType")
    assert type_out.startswith("-- Generated using lua-anot; do not edit manually.\nexport type MyType =  {\n")
    # current behavior keeps lua type values as quoted strings
    assert 'id: "number"' in type_out
