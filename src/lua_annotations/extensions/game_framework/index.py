from lua_annotations.api.annotations import (
    ENVIRONMENTS,
    AnnotationBuildCtx,
    AnnotationDef,
    Extension,
    ExtensionRegistry,
)
from lua_annotations.api.lua_dict import (
    HEADER,
    LuaPath,
    LuaPathResolver,
    convert_dict_module,
)
from lua_annotations.build_process import Environment, PostProcessCtx
from lua_annotations.parser_schemas import LuaType, ReturnedValue


def _env(ctx: AnnotationBuildCtx) -> Environment:
    return ctx.build_ctx.env


def _name(ctx: AnnotationBuildCtx) -> str | None:
    return ctx.annotation.kwargs_val.get('name')


class IndexExtension(Extension):
    def __init__(self) -> None:
        self.indexes: dict[Environment, dict[str, LuaPath] | LuaPath] = {env: {} for env in ENVIRONMENTS}
        self.exported_types: dict[Environment, list[tuple[LuaPath, str]]] = {env: [] for env in ENVIRONMENTS}
        self.indexed_types: dict[Environment, list[tuple[LuaPath, str, str]]] = {env: [] for env in ENVIRONMENTS}

    def on_post_process(self, ctx: PostProcessCtx):
        for env in ENVIRONMENTS:
            # module index
            ctx.create_file(env, 'Index.lua', convert_dict_module(ctx, self.indexes[env]))

            # type index
            resolver = LuaPathResolver(ctx.workspace)
            imports: dict[str, str] = {}
            type_lines: list[str] = []

            for path, type_name in self.exported_types[env]:
                type_lines.append(f'export type {type_name} = typeof({path.to_lua(resolver)})')

            for path, type_name, module_name in self.indexed_types[env]:
                imports.setdefault(module_name, f'local {module_name} = {path.to_lua(resolver)}')
                type_lines.append(f'export type {type_name} = {module_name}.{type_name}')

            # build final file
            out = [HEADER] + resolver.get_import_lines() + [''] + list(imports.values()) + type_lines + ['', 'return nil']
            ctx.create_file(env, 'TypeIndex.lua', '\n'.join(out))

    def on_build_indexed(self, ctx: AnnotationBuildCtx):
        module = ctx.annotation.adornee
        assert isinstance(module, ReturnedValue)

        indexed = self.indexes[_env(ctx)]
        key = _name(ctx) or module.returned_name
        value = module.get_path(require=True)

        argval = ctx.annotation.args_val
        if argval:
            assert isinstance(indexed, dict)
            indexed.setdefault(str(argval[0]), {})  # pyright: ignore[reportArgumentType]
            indexed[argval[0]][key] = value  # pyright: ignore[reportIndexIssue]
        else:
            indexed[key] = value  # pyright: ignore[reportIndexIssue]

    def on_build_export_type(self, ctx: AnnotationBuildCtx):
        module = ctx.annotation.adornee
        assert isinstance(module, ReturnedValue)

        self.exported_types[_env(ctx)].append((module.get_path(require=True), _name(ctx) or module.returned_name))

    def on_build_indexed_type(self, ctx: AnnotationBuildCtx):
        lua_type = ctx.annotation.adornee
        assert isinstance(lua_type, LuaType)
        assert lua_type.exported

        path = LuaPath(ctx.parser.file, require=True)
        self.indexed_types[_env(ctx)].append((path, _name(ctx) or lua_type.name, ctx.parser.file_name))

    def load(self, ctx: ExtensionRegistry) -> None:
        ctx.register_anot(
            AnnotationDef(
                'indexedType',
                scope='type',
                kwargs={'name': str},
                on_build=self.on_build_indexed_type,
            )
        )
        ctx.register_anot(
            AnnotationDef(
                'exportType',
                scope='returned_value',
                kwargs={'name': str},
                on_build=self.on_build_export_type,
            )
        )
        ctx.register_anot(
            AnnotationDef(
                'indexed',
                scope='returned_value',
                kwargs={'name': str},
                args=[str],
                on_build=self.on_build_indexed,
            )
        )
