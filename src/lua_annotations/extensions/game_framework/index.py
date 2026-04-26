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
    convert_dict_module,
)
from lua_annotations.build_process import Environment, PostProcessCtx
from lua_annotations.parser_schemas import LuaMethod, LuaModule, ReturnedValue


def _env(ctx: AnnotationBuildCtx) -> Environment:
    return ctx.build_ctx.env


def _name(ctx: AnnotationBuildCtx) -> str | None:
    return ctx.annotation.kwargs_val.get('name')


TYPEGEN_ANOTS = ('service', 'component', 'dependency')


def _dep_type_name(dep: str):
    if ':' not in dep:
        return dep

    return dep.split(':', 1)[1]


def _remote_dep(dep: str) -> tuple[Environment, str] | None:
    if ':' not in dep:
        return None

    remote_env, remote_name = dep.split(':', 1)
    if remote_env not in ENVIRONMENTS:
        return None

    return remote_env, remote_name


def _render_remote_type(methods: dict[str, LuaMethod]):
    if not methods:
        return '{}'

    out = '\n'
    for name, method in methods.items():
        out += f'    {name}: {method.generate_type()},\n'

    return '{' + out + '}'


class IndexExtension(Extension):
    def __init__(self) -> None:
        self.indexes: dict[Environment, dict[str, LuaPath] | LuaPath] = {env: {} for env in ENVIRONMENTS}
        self.module_types: dict[Environment, dict[str, str]] = {env: {} for env in ENVIRONMENTS}
        self.dep_types: dict[Environment, dict[str, str]] = {env: {} for env in ENVIRONMENTS}
        self.remote_methods: dict[Environment, dict[str, dict[str, LuaMethod]]] = {env: {} for env in ENVIRONMENTS}
        self.remote_type_refs: dict[Environment, dict[str, Environment]] = {env: {} for env in ENVIRONMENTS}

    def on_post_process(self, ctx: PostProcessCtx):
        for env in ENVIRONMENTS:
            # module index
            ctx.create_file(env, 'Index.lua', convert_dict_module(ctx, self.indexes[env]))
            out: list[str] = []
            type_defs = dict(self.module_types[env])

            for name, remote_env in self.remote_type_refs[env].items():
                methods = self.remote_methods[remote_env].get(name, {})
                type_defs[name] = _render_remote_type(methods)

            for name, data in type_defs.items():
                out.append(f'export type {name} = {data}')

            for name, data in self.dep_types[env].items():
                out.append(f'export type {name} = {data}')

            ctx.create_file(env, 'ServiceTypes.lua', '\n'.join([HEADER, ''] + out + ['', 'return nil\n']))

    def on_file_process(self, ctx: FileBuildCtx):
        env = ctx.build_ctx.env
        for anot in ctx.parser.annotations:
            if anot.name == 'remote':
                method = anot.adornee
                assert isinstance(method, LuaMethod)

                module_name = method.module.returned_name
                self.remote_methods[env].setdefault(module_name, {})
                self.remote_methods[env][module_name][method.name] = method

            if anot.name in TYPEGEN_ANOTS:
                # service typegen
                module = anot.adornee
                assert isinstance(module, LuaModule)

                typegen = anot.kwargs_val.get('typegen')
                out_type = None

                if typegen == 'registry':
                    load_after = anot.kwargs_val.get('load_after')
                    load_after_type = load_after[0] if load_after else 'any'
                    out_type = '{' + f'[Instance]: {load_after_type}' + '}'
                else:
                    out_type = module.generate_type()

                self.module_types[env][module.returned_name] = out_type

            if anot.name in TYPEGEN_ANOTS or anot.name == 'initService':
                # deps types
                deps = anot.kwargs_val.get('depends', [])
                dep_names = [_dep_type_name(dep) for dep in deps]
                dep_string = '{' + ', '.join([f'{dep}: {dep}' for dep in dep_names]) + '}'

                for dep in deps:
                    remote_dep = _remote_dep(dep)
                    if not remote_dep:
                        continue

                    remote_env, remote_name = remote_dep
                    self.remote_type_refs[env].setdefault(remote_name, remote_env)

                if len(dep_string) > 2:  # not {}
                    self.dep_types[env][f'{anot.get_adornee_name()}Deps'] = dep_string

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
