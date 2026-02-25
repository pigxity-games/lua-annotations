from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING
from api.annotations import ENVIRONMENTS, AnnotationBuildCtx, AnnotationDef, ExtensionRegistry, Extension, scope
from api.arguments import default_list
from build_process import Environment, PostProcessCtx
from exceptions import BuildError
from parser_schemas import Annotation, LuaMethod

if TYPE_CHECKING:
    from lua_extension_anots import ManifestExtension


def filter_deps(deps: list[str]):
    return [d for d in deps if ':' not in d]


def proc_deps(deps: list[str]):
    out = {'services': [], 'remotes': []}
    for dep in deps:
        if ':' in dep:
            out['remotes'].append(dep.split(':')[1])
        else:
            out['services'].append(dep)
    return out

class LifecycleExtension(Extension):
    def __init__(self):
        self.services: dict[Environment, list[Annotation]] = {env: [] for env in ENVIRONMENTS}

    def add_service(self, ctx: AnnotationBuildCtx):
        self.services[ctx.build_ctx.env].append(ctx.annotation)

    def on_post_process(self, ctx: PostProcessCtx):
        for env in ('server', 'client'):
            services = self.services[env] + self.services['shared']

            self.manifestExt.manifest[env]['services'] = {svc.adornee.returned_name: (
            {
                'depends': proc_deps(svc.kwargs_val.get('depends', [])),
                'getAdornee': svc.adornee.get_path(function=True, require=True),
                'kind': svc.name
            }
                | ({'tags': svc.args_val[0]} if svc.name == 'component' else {})
            )
            for svc in services}

            sorter = TopologicalSorter({svc.adornee.returned_name: filter_deps(svc.kwargs_val.get('depends', {})) for svc in services})
            
            try:
                self.manifestExt.manifest[env]['load_order'] = list(sorter.static_order())
            except CycleError as e:
                raise BuildError(f"Cycle detected for service graph: {e.args}") from e

    def load(self, ctx: ExtensionRegistry):
        self.manifestExt: ManifestExtension = ctx.extensions['ManifestExtension']

        ctx.register_anot(AnnotationDef('service', retention='build', kwargs={'depends': default_list}, on_build=self.add_service))
        ctx.register_anot(AnnotationDef('component', retention='build', args=[default_list], kwargs={'depends': default_list}, on_build=self.add_service))
        ctx.register_anot(AnnotationDef('bindTag', retention='init', args=[default_list], scope='method'))