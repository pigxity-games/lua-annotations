from typing import TYPE_CHECKING, Any

from lua_annotations.api.annotations import (
    AnnotationBuildCtx,
    AnnotationDef,
    ExtensionRegistry,
    Extension,
)
from lua_annotations.api.arguments import bool_arg, default_list, literal_builder
from lua_annotations.build_process import Environment, PostProcessCtx
from lua_annotations.exceptions import BuildError
from lua_annotations.parser_schemas import Annotation, LuaMethod

if TYPE_CHECKING:
    from lua_annotations.extensions.default import ManifestExtension

REMOTE_INSTANCE_MAP = {
    'function': 'RemoteFunction',
    'event': 'RemoteEvent',
    'unreliable': 'UnreliableRemoteEvent',
}

REMOTE_TYPES = list(REMOTE_INSTANCE_MAP.keys())
MIDDLEWARE_ENVIRONMENTS = ['server', 'client']
MIDDLEWARE_DIRECTIONS = ['inbound', 'outbound']


class NetworkingExtension(Extension):
    def __init__(self):
        self.remotes: dict[Any, Any] = {}
        self.manifestExt: ManifestExtension | None = None

    def remote_on_build(self, ctx: AnnotationBuildCtx):
        if ctx.build_ctx.env == 'shared':
            raise BuildError('@remote annotations are only valid in client or server code')
        assert self.manifestExt

        anot: Annotation = ctx.annotation
        adornee = anot.adornee
        assert isinstance(adornee, LuaMethod)

        class_name = REMOTE_INSTANCE_MAP[ctx.annotation.args_val[0]]
        module_name = adornee.module.returned_name

        anot.export_data['remote_name'] = adornee.name
        anot.export_data['remote_parent'] = module_name
        anot.export_data['remote_env'] = ctx.build_ctx.env

        self.remotes.setdefault(module_name, {'ClassName': 'Folder', 'Children': {}})
        self.remotes[module_name]['Children'][adornee.name] = {'ClassName': class_name}
        for env in ('server', 'client'):
            self.manifestExt.add_module_data(
                env,
                module_name,
                adornee.module.get_path(require=True, cache=True),
                {
                    'remotes': {
                        ctx.build_ctx.env: {
                            adornee.name: {
                                'service': module_name,
                                'method': adornee.name,
                                'remoteType': ctx.annotation.args_val[0],
                                'middleware': ctx.annotation.kwargs_val.get('middleware', []),
                            }
                        }
                    }
                },
            )

    def middleware_on_build(self, ctx: AnnotationBuildCtx):
        anot: Annotation = ctx.annotation
        adornee = anot.adornee
        assert isinstance(adornee, LuaMethod)

        anot.export_data['middleware_name'] = anot.kwargs_val.get('name', adornee.name)

    def on_post_process(self, ctx: PostProcessCtx):
        # Convert dict to valid .model.json format
        root_children = []

        for module_name, module_data in self.remotes.items():
            module_children_map = module_data.get('Children', {})
            module_children = []

            for remote_name, remote_data in module_children_map.items():
                module_children.append(
                    {
                        'Name': remote_name,
                        'ClassName': remote_data['ClassName'],
                    }
                )

            root_children.append(
                {
                    'Name': module_name,
                    'ClassName': 'Folder',
                    'Children': module_children,
                }
            )

        model = {
            'ClassName': 'Folder',
            'Children': root_children,
        }

        ctx.dump_json('shared', 'Remotes.model.json', model)

    def load(self, ctx: ExtensionRegistry):
        from lua_annotations.extensions.default import ManifestExtension

        manifest_ext = ctx.extensions.get('ManifestExtension')
        assert isinstance(manifest_ext, ManifestExtension)

        self.manifestExt = manifest_ext

        ctx.register_anot(
            AnnotationDef(
                'remote',
                scope='method',
                retention='init',
                args=[literal_builder(REMOTE_TYPES)],
                kwargs={'middleware': default_list},
                on_build=self.remote_on_build,
            )
        )
        ctx.register_anot(
            AnnotationDef(
                'middleware',
                scope='method',
                retention='init',
                args=[
                    literal_builder(MIDDLEWARE_ENVIRONMENTS),
                    literal_builder(MIDDLEWARE_DIRECTIONS),
                ],
                kwargs={
                    'global': bool_arg,
                    'name': str,
                },
                on_build=self.middleware_on_build,
            )
        )
