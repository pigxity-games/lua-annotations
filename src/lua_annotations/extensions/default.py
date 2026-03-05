from typing import Any

from lua_annotations.api.annotations import (
    ENVIRONMENTS,
    AnnotationBuildCtx,
    AnnotationDef,
    ExtensionRegistry,
    Extension,
    FileBuildCtx,
)
from lua_annotations.build_process import Environment, PostProcessCtx, get_template
from lua_annotations.parser_schemas import LuaMethod
from lua_annotations.api.lua_dict import LuaPathResolver, convert_dict


class ManifestExtension(Extension):
    def __init__(self):
        self.manifest: dict[Environment, dict[Any, Any]] = {env: {} for env in ENVIRONMENTS}
        for env in ENVIRONMENTS:
            self.manifest[env]['anot_hooks'] = {}
            self.manifest[env]['init_hooks'] = []
            self.manifest[env]['post_init_hooks'] = []
            self.manifest[env]['annotations'] = []

    def on_build_post_init(self, ctx: AnnotationBuildCtx, key: str):
        adornee = ctx.annotation.adornee
        assert isinstance(adornee, LuaMethod)

        self.manifest[ctx.build_ctx.env][key].append(adornee.get_path(require=True))

    def on_build_annotation_init(self, ctx: AnnotationBuildCtx):
        adornee = ctx.annotation.adornee
        assert isinstance(adornee, LuaMethod)

        self.manifest[ctx.build_ctx.env]['anot_hooks'][ctx.annotation.adornee.name] = adornee.get_path(require=True)

    def load(self, ctx: ExtensionRegistry):
        ctx.register_anot(
            AnnotationDef(
                name='onInit',
                scope='method',
                on_build=lambda ctx: self.on_build_post_init(ctx, 'init_hooks'),
            )
        )
        ctx.register_anot(
            AnnotationDef(
                'onPostInit',
                scope='method',
                on_build=lambda ctx: self.on_build_post_init(ctx, 'post_init_hooks'),
            )
        )
        ctx.register_anot(
            AnnotationDef(
                name='annotationInit',
                scope='method',
                on_build=self.on_build_annotation_init,
            )
        )

        # annotation to literally just mark a module to be parsed.
        ctx.register_anot(AnnotationDef(name='module', scope='module'))

    def on_file_process(self, ctx: FileBuildCtx):
        for anot in ctx.parser.annotations:
            if anot.adef.retention != 'build':
                self.manifest[ctx.build_ctx.env]['annotations'].append(anot)

    def on_post_process(self, ctx: PostProcessCtx):
        for env in ('server', 'client'):
            template = get_template('AnnotationInit.lua')

            for key in ('annotations', 'anot_hooks', 'init_hooks', 'post_init_hooks'):
                if isinstance(self.manifest[env][key], dict):
                    self.manifest[env][key] |= self.manifest['shared'][key]
                else:
                    self.manifest[env][key] += self.manifest['shared'][key]
            data = self.manifest[env]

            converted = convert_dict(LuaPathResolver(ctx.workspace), data, prefix='local manifest =')
            out = template.replace('--manifest', converted)

            ctx.create_file(env, f'AnnotationInit.{env}.lua', out)


def load(ctx: ExtensionRegistry):
    ctx.register_extension(ManifestExtension())
