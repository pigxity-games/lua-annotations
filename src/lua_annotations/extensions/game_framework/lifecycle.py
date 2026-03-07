from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING

from lua_annotations.api.annotations import (
    ENVIRONMENTS,
    AnnotationBuildCtx,
    AnnotationDef,
    ExtensionRegistry,
    Extension,
)
from lua_annotations.api.arguments import default_list
from lua_annotations.build_process import Environment, PostProcessCtx, logger
from lua_annotations.exceptions import BuildError
from lua_annotations.parser_schemas import Annotation, ReturnedValue

if TYPE_CHECKING:
    from lua_annotations.extensions.default import ManifestExtension


def filter_deps(deps: list[str]) -> list[str]:
    return [d for d in deps if ':' not in d]


def dep_error(svc: Annotation, dep: str, msg: str):
        raise BuildError(msg + get_service_name(svc) + ': ' + dep)


def proc_deps(svc: Annotation, service_map: dict[str, Annotation]):
    out = {'services': [], 'remotes': []}

    if svc.name == 'component':
        out['components'] = []

    for dep in svc.kwargs_val.get('depends', []):
        if ':' in dep:
            out['remotes'].append(dep.split(':')[1])
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


def service_todict(svc: Annotation, service_map: dict[str, Annotation]):    
    out = {
        'depends': proc_deps(svc, service_map),
        'getAdornee': svc.adornee.get_path(function=True, require=True),  # pyright: ignore[reportAttributeAccessIssue]
        'kind': svc.name,
    }
    
    if svc.name == 'component':
        out['tags'] = svc.args_val[0]
        
        data_svc = svc.kwargs_val.get('data', [])
        if data_svc and not service_map.get(data_svc):
            logger().warn(f'Invalid data dependency for component {get_service_name(svc)}: "{data_svc}"; ommiting')
        else:
            out['data_service'] = data_svc

    return out


def get_service_name(svc: Annotation):
    assert isinstance(svc.adornee, ReturnedValue)
    return svc.adornee.returned_name


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
        self.manifestExt: ManifestExtension | None = None

    def add_service(self, ctx: AnnotationBuildCtx):
        self.services[ctx.build_ctx.env].append(ctx.annotation)

    def on_post_process(self, ctx: PostProcessCtx):
        assert self.manifestExt

        for env in ('server', 'client'):
            services = self.services[env] + self.services['shared']

            self.manifestExt.manifest[env]['services'] = {
                get_service_name(svc): service_todict(svc, {get_service_name(svc): svc for svc in services})
                for svc in services
                if svc.name != 'dependency'
            }

            try:
                self.manifestExt.manifest[env]['load_order'] = get_runtime_load_order(services)
            except CycleError as e:
                raise BuildError(f"Cycle detected for service graph: {e.args}") from e

    def load(self, ctx: ExtensionRegistry):
        from lua_annotations.extensions.default import ManifestExtension

        manifest_ext = ctx.extensions.get('ManifestExtension')
        assert isinstance(manifest_ext, ManifestExtension)

        self.manifestExt = manifest_ext

        dependency = AnnotationDef(
            'dependency',
            retention='build',
            kwargs={'load_after': default_list},
            on_build=self.add_service,
        )
        ctx.register_anot(dependency)

        ctx.register_anot(dependency.extend(AnnotationDef('service', kwargs={'depends': default_list})))
        ctx.register_anot(
            AnnotationDef(
                'component',
                retention='build',
                args=[default_list],
                kwargs={'depends': default_list, 'data': str},
                on_build=self.add_service,
            )
        )
        ctx.register_anot(AnnotationDef('bindTag', retention='init', args=[default_list], scope='method'))
