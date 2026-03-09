from typing import override
from lua_annotations.api.annotations import (
    ENVIRONMENTS,
    AnnotationBuildCtx,
    AnnotationDef,
    Extension,
    ExtensionRegistry,
    FileBuildCtx,
)
from lua_annotations.api.lua_dict import (
    HEADER,
    LuaPath,
    LuaPathResolver,
    convert_dict_module,
)
from lua_annotations.build_process import Environment, PostProcessCtx
from lua_annotations.parser_schemas import LuaModule, LuaType, ReturnedValue


def _env(ctx: AnnotationBuildCtx) -> Environment:
    return ctx.build_ctx.env


def _name(ctx: AnnotationBuildCtx) -> str | None:
    return ctx.annotation.kwargs_val.get('name')


TYPEGEN_ANOTS = ('service', 'component', 'dependency')


class IndexExtension(Extension):
    def __init__(self) -> None:
        self.indexes: dict[Environment, dict[str, LuaPath] | LuaPath] = {env: {} for env in ENVIRONMENTS}
        self.global_types_file: dict[Environment, list[str]] = {env: [] for env in ENVIRONMENTS}

    def on_post_process(self, ctx: PostProcessCtx):
        for env in ENVIRONMENTS:
            # module index
            ctx.create_file(env, 'Index.lua', convert_dict_module(ctx, self.indexes[env]))
            ctx.create_file(env, 'ServiceTypes.lua', '\n'.join([HEADER, ''] + self.global_types_file[env] + ['', 'return nil\n']))

    def on_file_process(self, ctx: FileBuildCtx):
        env = ctx.build_ctx.env
        for anot in ctx.parser.annotations:
            if anot.name in TYPEGEN_ANOTS:
                # service typegen
                module = anot.adornee
                assert isinstance(module, LuaModule)

                typegen = anot.kwargs_val.get('typegen')
                out_type = None

                if typegen == 'registry':
                    load_after = anot.kwargs_val.get('load_after')
                    out_type = '{' + f'[Instance]: {load_after[0] if load_after and len(load_after) > 0 else 'any'}' + '}'
                else:
                    out_type = module.generate_type()

                self.global_types_file[env].append(f'export type {module.returned_name} = {out_type}')

            if anot.name in TYPEGEN_ANOTS or anot.name == 'initService':
                # deps types
                deps = anot.kwargs_val.get('depends', [])
                dep_string = '{' + ', '.join([f'{dep}: {dep}' for dep in deps]) + '}'

                if len(dep_string) > 2:  # not {}
                    self.global_types_file[env].append(f'export type {anot.get_adornee_name()}Deps = {dep_string}')

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

        path = LuaPath(ctx.parser.file, require=True)

    def load(self, ctx: ExtensionRegistry) -> None:
        ctx.register_anot(
            AnnotationDef(
                'indexed',
                scope='returned_value',
                kwargs={'name': str},
                args=[str],
                on_build=self.on_build_indexed,
            )
        )
