from typing import Any
from api.annotations import ENVIRONMENTS, AnnotationBuildCtx, AnnotationDef, ExtensionRegistry, Extension, FileBuildCtx
from build_process import Environment, PostProcessCtx
from parser_schemas import LuaMethod
from api.lua_dict import LuaPathResolver, convert_dict


class ManifestExtension(Extension):
    def __init__(self):
        self.manifest: dict[Environment, dict[Any, Any]] = {env: {} for env in ENVIRONMENTS}
        for env in ENVIRONMENTS:
            self.manifest[env]['anot_hooks'] = []
            self.manifest[env]['init_hooks'] = []
            self.manifest[env]['annotations'] = []

    def on_build(self, key: str, ctx: AnnotationBuildCtx):
        adornee = ctx.annotation.adornee
        assert isinstance(adornee, LuaMethod)

        self.manifest[ctx.build_ctx.env][key].append(adornee.get_path(require=True))

    def load(self, ctx: ExtensionRegistry):
        ctx.register_anot(AnnotationDef(
            'onPostInit',
            scope='method',
            on_build= lambda ctx: self.on_build('init_hooks', ctx) 
        ))
        ctx.register_anot(AnnotationDef(
            name='annotationInit',
            scope='method',
            on_build= lambda ctx: self.on_build('anot_hooks', ctx)
        ))

        #annotation to literally just mark a module to be parsed.
        ctx.register_anot(AnnotationDef(
            name='module',
            scope='module'
        ))

    def on_file_process(self, ctx: FileBuildCtx):
        for anot in ctx.parser.annotations:
            if anot.adef.retention != 'build':
                self.manifest[ctx.build_ctx.env]['annotations'].append(anot)

    def on_post_process(self, ctx: PostProcessCtx):
        for env in ('server', 'client'):
            with open('./templates/AnnotationInit.lua') as f:
                template = f.read()

            data = self.manifest[env] | self.manifest['shared']
            converted = convert_dict(LuaPathResolver(ctx.workspace), data, prefix = 'local manifest =')
            out = template.replace('--manifest', converted)

            ctx.create_file(env, f'AnnotationInit.{env}.lua', out)


def load(ctx: ExtensionRegistry):
    ctx.register_extension(ManifestExtension())