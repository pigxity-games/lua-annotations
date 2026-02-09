from annotations import ENVIRONMENTS, AnnotationBuildCtx, AnnotationDef, AnnotationRegistry, Extension
from build_process import Environment, PostProcessCtx
from lua_dict import HEADER, LuaPath, LuaPathResolver, convert_dict
from parser_schemas import LuaModule, LuaType


def _env(ctx: AnnotationBuildCtx):
    return ctx.build_ctx.env


class IndexExtension(Extension):
    def __init__(self) -> None:
        self.indexes: dict[Environment, dict[str, LuaPath]]                     = {env: {} for env in ENVIRONMENTS}
        self.exported_types: dict[Environment, list[tuple[LuaPath, str]]]       = {env: [] for env in ENVIRONMENTS}
        self.indexed_types: dict[Environment, list[tuple[LuaPath, str, str]]]   = {env: [] for env in ENVIRONMENTS}


    def on_post_process(self, ctx: PostProcessCtx):
        for env in ENVIRONMENTS:
            # module index
            ctx.create_file(env, 'Index.lua', convert_dict(ctx, self.indexes[env]))

            # type index
            resolver = LuaPathResolver(ctx)
            imports: dict[str, str] = {}
            type_lines: list[str] = []

            for path, type_name in self.exported_types[env]:
                type_lines.append(f'export type {type_name} = typeof({path.to_lua(resolver)})')

            for path, type_name, module_name in self.indexed_types[env]:
                imports.setdefault(module_name, f'local {module_name} = {path.to_lua(resolver)}')
                type_lines.append(f'export type {type_name} = {module_name}.{type_name}')

            # build final file
            out = (
                [HEADER]
                + resolver.get_import_lines()
                + ['']
                + list(imports.values())
                + type_lines
                + ['', 'return nil']
            )
            ctx.create_file(env, 'Types.lua', '\n'.join(out))


    def on_build_indexed(self, ctx: AnnotationBuildCtx):
        module = ctx.annotation.adornee
        assert isinstance(module, LuaModule)

        self.indexes[_env(ctx)][module.returned_name] = LuaPath(ctx.parser.file, require=True)


    def on_build_export_type(self, ctx: AnnotationBuildCtx):
        module = ctx.annotation.adornee
        assert isinstance(module, LuaModule)

        path = LuaPath(ctx.parser.file, require=True)
        self.exported_types[_env(ctx)].append((path, module.returned_name))


    def on_build_indexed_type(self, ctx: AnnotationBuildCtx):
        lua_type = ctx.annotation.adornee
        assert isinstance(lua_type, LuaType)
        assert lua_type.exported

        path = LuaPath(ctx.parser.file, require=True)
        self.indexed_types[_env(ctx)].append((path, lua_type.name, ctx.parser.file_name))


    def load(self, ctx: AnnotationRegistry) -> None:
        ctx.registerAnot(AnnotationDef('indexed', retention='build', on_build=self.on_build_indexed))
        ctx.registerAnot(AnnotationDef('exportType', retention='build', on_build=self.on_build_export_type))
        ctx.registerAnot(AnnotationDef('indexedType', scope='type', retention='build', on_build=self.on_build_indexed_type))