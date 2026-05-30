from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING

from lua_annotations.api.annotations import (
    ENVIRONMENTS,
    AnnotationBuildCtx,
    AnnotationDef,
    ExtensionRegistry,
    Extension,
    FileBuildCtx,
)
from lua_annotations.api.arguments import default_list
from lua_annotations.api.manifest import ServiceEntry
from lua_annotations.build_process import Environment, PostProcessCtx, logger
from lua_annotations.exceptions import BuildError
from lua_annotations.parser_schemas import Annotation, LuaMethod, ReturnedValue

from importlib.resources import files

if TYPE_CHECKING:
    from lua_annotations.extensions.default import ManifestExtension


def filter_deps(deps: list[str]) -> list[str]:
    return [d for d in deps if ':' not in d]


def remote_dep(dep: str) -> tuple[Environment, str] | None:
    if ':' not in dep:
        return None

    remote_env, remote_name = dep.split(':', 1)
    if remote_env not in ENVIRONMENTS:
        return None

    return remote_env, remote_name


def dep_error(svc: Annotation, dep: str, msg: str):
    raise BuildError(msg + get_service_name(svc) + ': ' + dep)


def proc_deps(
    svc: Annotation,
    service_map: dict[str, Annotation],
    remote_map: dict[Environment, set[str]],
):
    out = {'services': [], 'remotes': []}

    if svc.name == 'component':
        out['components'] = []

    for dep in svc.kwargs_val.get('depends', []):
        if ':' in dep:
            remote = remote_dep(dep)
            if not remote:
                dep_error(svc, dep, 'Invalid remote dependency for service')
            assert remote is not None

            remote_env, remote_name = remote
            if remote_name not in remote_map[remote_env]:
                dep_error(svc, dep, 'Invalid remote dependency for service')

            out['remotes'].append(remote_name)
            continue

        dep_anot = service_map.get(dep)
        if not dep_anot:
            dep_error(svc, dep, f'Invalid dependency for service')

        if dep_anot.name == 'component':  # pyright: ignore[reportOptionalMemberAccess]
            if svc.name != 'component':
                dep_error(svc, dep, f'Tried to import component in service:')

            out['components'].append(dep)
        else:
            out['services'].append(dep)

    return out


def service_todict(
    svc: Annotation,
    service_map: dict[str, Annotation],
    remote_map: dict[Environment, set[str]],
):
    tags = None
    data_service = None

    if svc.name == 'component':
        tags = svc.args_val[0]

        data_svc = svc.kwargs_val.get('data', None)
        if data_svc and not service_map.get(data_svc):
            logger().warn(f'Invalid data dependency for component {get_service_name(svc)}: "{data_svc}"; ommiting')
        elif data_svc:
            data_service = data_svc

    return ServiceEntry(
        depends=proc_deps(svc, service_map, remote_map),
        kind=svc.name,
        tags=tags,
        data_service=data_service,
    )


def get_service_name(svc: Annotation):
    if isinstance(svc.adornee, ReturnedValue):
        return svc.adornee.returned_name
    if isinstance(svc.adornee, LuaMethod):
        return svc.adornee.name
    raise BuildError(f'Unknown service adornee type: {type(svc.adornee).__name__}')


def get_topo_graph(services: list[Annotation], key: str):
    return {get_service_name(svc): filter_deps(svc.kwargs_val.get(key, [])) for svc in services}


def merge_graphs(*graphs: dict[str, list[str]]):
    merged: dict[str, list[str]] = {}

    for graph in graphs:
        for node, deps in graph.items():
            merged.setdefault(node, [])

            for dep in deps:
                if dep not in merged[node]:
                    merged[node].append(dep)

    return merged


def get_runtime_load_order(services: list[Annotation]):
    graph = merge_graphs(
        get_topo_graph(services, 'depends'),
        get_topo_graph(services, 'load_after'),
    )

    runtime_load_exclude = {get_service_name(svc) for svc in services if svc.name == 'dependency'}
    sorter = TopologicalSorter(graph)
    return [name for name in sorter.static_order() if name not in runtime_load_exclude]


type AnotDict = dict[Environment, list[Annotation]]


class LifecycleExtension(Extension):
    def __init__(self):
        self.services: AnotDict = {env: [] for env in ENVIRONMENTS}
        self.dependencies: AnotDict = {env: [] for env in ENVIRONMENTS}
        self.remote_services: dict[Environment, set[str]] = {env: set() for env in ENVIRONMENTS}
        self.manifestExt: ManifestExtension | None = None

    def add_service(self, ctx: AnnotationBuildCtx):
        self.services[ctx.build_ctx.env].append(ctx.annotation)

    def on_file_process(self, ctx: FileBuildCtx):
        for anot in ctx.parser.annotations:
            if anot.name != 'remote':
                continue

            adornee = anot.adornee
            assert isinstance(adornee, LuaMethod)
            self.remote_services[ctx.build_ctx.env].add(adornee.module.returned_name)

    def on_post_process(self, ctx: PostProcessCtx):
        assert self.manifestExt

        for env_name, services in self.services.items():
            all_services = services
            if env_name != 'shared':
                all_services = services + self.services['shared']

            entry_map = {
                get_service_name(svc): service_todict(
                    svc,
                    {get_service_name(svc): svc for svc in all_services},
                    self.remote_services,
                )
                for svc in services
            }

            for svc in services:
                service_name = get_service_name(svc)
                module = svc.get_module()
                assert isinstance(module, ReturnedValue)
                module_path = module.get_path(require=True, cache=True, cache_name=service_name)
                self.manifestExt.update_module_data(env_name, service_name, module_path, entry_map[service_name])

        for env in ('server', 'client'):
            services = self.services[env] + self.services['shared']

            try:
                self.manifestExt.set_load_order(env, get_runtime_load_order(services))
            except CycleError as e:
                raise BuildError(f'Cycle detected for service graph: {e.args}') from e

    def load(self, ctx: ExtensionRegistry):
        from lua_annotations.extensions.default import ManifestExtension

        manifest_ext = ctx.extensions.get('ManifestExtension')
        assert isinstance(manifest_ext, ManifestExtension)

        self.manifestExt = manifest_ext
        manifest_functions = files('lua_annotations') / 'extensions' / 'game_framework' / 'lua' / 'ManifestFunctions.lua'
        manifest_ext.register_manifest_functions('shared', manifest_functions.read_text())

        dependency = AnnotationDef(
            'dependency',
            retention='build',
            kwargs={'depends': default_list, 'load_after': default_list, 'typegen': str},
            on_build=self.add_service,
        )

        ctx.register_anot(dependency)
        ctx.register_anot(dependency.extend(AnnotationDef('initService', scope='method')))
        ctx.register_anot(dependency.extend(AnnotationDef('service')))
        ctx.register_anot(
            dependency.extend(
                AnnotationDef(
                    'component',
                    args=[default_list],
                    kwargs={'data': str},
                )
            )
        )

        ctx.register_anot(AnnotationDef('bindTag', retention='init', args=[default_list], scope='method'))

        t = files('lua_annotations') / 'extensions' / 'game_framework' / 'lua' / 'Lifecycle.lua'
        ctx.add_file('shared', 'Lifecycle.lua', t.read_text())
