from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING, Any

from lua_annotations.api.annotations import ENVIRONMENTS, AnnotationBuildCtx, AnnotationDef, ExtensionRegistry, Extension
from lua_annotations.api.arguments import default_list
from lua_annotations.build_process import Environment, PostProcessCtx
from lua_annotations.exceptions import BuildError
from lua_annotations.parser_schemas import Annotation, ReturnedValue

if TYPE_CHECKING:
    from lua_annotations.extensions.default import ManifestExtension


def filter_deps(deps: list[str]) -> list[str]:
    return [d for d in deps if ':' not in d]


def proc_deps(deps: list[str]) -> dict[str, list[str]]:
    out = {'services': [], 'remotes': []}
    for dep in deps:
        if ':' in dep:
            out['remotes'].append(dep.split(':')[1])
        else:
            out['services'].append(dep)
    return out

def get_topo_graph(services: list[Annotation], key: str) -> dict[str, list[str]]:
    return {svc.adornee.returned_name: filter_deps(svc.kwargs_val.get(key, {})) for svc in services}  # pyright: ignore[reportAttributeAccessIssue]

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

            self.manifestExt.manifest[env]['services'] = {svc.adornee.returned_name: (  # pyright: ignore[reportAttributeAccessIssue]
            {
                'depends': proc_deps(svc.kwargs_val.get('depends', [])),
                'getAdornee': svc.adornee.get_path(function=True, require=True),  # pyright: ignore[reportAttributeAccessIssue]
                'kind': svc.name
            }
                | ({'tags': svc.args_val[0]} if svc.name == 'component' else {})
            )
            for svc in services if svc.name != 'dependency'}

            load_after_graph = get_topo_graph(services, 'load_after')
            runtime_load_exclude = tuple(load_after_graph.keys())

            sorter = TopologicalSorter(get_topo_graph(services, 'depends') | load_after_graph)
            
            try:
                self.manifestExt.manifest[env]['load_order'] = list([s for s in sorter.static_order() if s not in runtime_load_exclude])
            except CycleError as e:
                raise BuildError(f"Cycle detected for service graph: {e.args}") from e

    def load(self, ctx: ExtensionRegistry):
        from lua_annotations.extensions.default import ManifestExtension

        manifest_ext = ctx.extensions.get('ManifestExtension')
        assert isinstance(manifest_ext, ManifestExtension)

        self.manifestExt = manifest_ext

        dependency = AnnotationDef('dependency', retention='build', kwargs={'load_after': default_list}, on_build=self.add_service)
        ctx.register_anot(dependency)

        ctx.register_anot(dependency.extend(AnnotationDef('service', kwargs={'depends': default_list})))
        ctx.register_anot(AnnotationDef('component', retention='build', args=[default_list], kwargs={'depends': default_list}, on_build=self.add_service))
        ctx.register_anot(AnnotationDef('bindTag', retention='init', args=[default_list], scope='method'))
