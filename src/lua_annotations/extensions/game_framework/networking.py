from typing import TYPE_CHECKING, Any

from lua_annotations.api.annotations import (
    AnnotationBuildCtx,
    AnnotationDef,
    ExtensionRegistry,
    Extension,
)
from lua_annotations.api.arguments import bool_arg, default_list, literal_builder
from lua_annotations.api.manifest import ManifestRemotes, RemoteEntry
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
        self.remote_info: dict[Environment, dict[str, dict[str, RemoteEntry]]] = {'client': {}, 'server': {}}
        self.manifestExt: ManifestExtension | None = None

    def remote_on_build(self, ctx: AnnotationBuildCtx):
        if ctx.build_ctx.env == 'shared':
            raise BuildError('@remote annotations are only valid in client or server code')

        anot: Annotation = ctx.annotation
        adornee = anot.adornee
        assert isinstance(adornee, LuaMethod)

        class_name = REMOTE_INSTANCE_MAP[ctx.annotation.args_val[0]]
        module_name = adornee.module.returned_name

        assert self.manifestExt
        self.manifestExt.update_annotation_data(
            anot,
            {
                'remote_name': adornee.name,
                'remote_parent': module_name,
            },
        )

        self.remotes.setdefault(module_name, {'ClassName': 'Folder', 'Children': {}})
        self.remotes[module_name]['Children'][adornee.name] = {'ClassName': class_name}

        module_info = self.remote_info[ctx.build_ctx.env].setdefault(module_name, {})
        module_info[adornee.name] = RemoteEntry(
            service=module_name,
            method=adornee.name,
            remoteType=ctx.annotation.args_val[0],
            middleware=ctx.annotation.kwargs_val.get('middleware', []),
        )

    def middleware_on_build(self, ctx: AnnotationBuildCtx):
        anot: Annotation = ctx.annotation
        adornee = anot.adornee
        assert isinstance(adornee, LuaMethod)

        assert self.manifestExt
        self.manifestExt.update_annotation_data(
            anot,
            {
                'middleware_name': anot.kwargs_val.get('name', adornee.name),
            },
        )

    def write_remote_info(self):
        assert self.manifestExt

        self.manifestExt.set_remotes(ManifestRemotes(client=self.remote_info['client'], server=self.remote_info['server']))

    def on_post_process(self, ctx: PostProcessCtx):
        self.write_remote_info()

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
