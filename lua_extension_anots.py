from api.annotations import ENVIRONMENTS, AnnotationBuildCtx, AnnotationDef, AnnotationRegistry, Extension, FileBuildCtx
from build_process import Environment, PostProcessCtx
from parser_schemas import Annotation, LuaMethod
from api.lua_dict import LuaPath, LuaPathResolver, convert_dict


type D = dict[Environment, list[LuaPath]]

def on_build(dict: D, ctx: AnnotationBuildCtx):
    adornee = ctx.annotation.adornee
    assert isinstance(adornee, LuaMethod)

    dict[ctx.build_ctx.env].append(adornee.get_path(require=True))


class ManifestExtension(Extension):
    def __init__(self):
        self.post_init_hooks: D = {env: [] for env in ENVIRONMENTS}
        self.anot_init_hooks: D = {env: [] for env in ENVIRONMENTS}
        self.anot_entries: dict[Environment, list[Annotation]] = {env: [] for env in ENVIRONMENTS}

    def load(self, ctx: AnnotationRegistry):
        ctx.registerAnot(AnnotationDef(
            'onPostInit',
            scope='method',
            on_build= lambda ctx: on_build(self.post_init_hooks, ctx) 
        ))
        ctx.registerAnot(AnnotationDef(
            name='annotationInit',
            scope='method',
            on_build= lambda ctx: on_build(self.anot_init_hooks, ctx)
        ))

        #annotation to literally just mark a module to be parsed.
        ctx.registerAnot(AnnotationDef(
            name='module',
            scope='module'
        ))

    def on_file_process(self, ctx: FileBuildCtx):
        for anot in ctx.parser.annotations:
            if anot.adef.retention != 'build':
                self.anot_entries[ctx.build_ctx.env].append(anot)

    def on_post_process(self, ctx: PostProcessCtx):
        for env in ('server', 'client'):
            with open('./templates/AnnotationInit.lua') as f:
                template = f.read()

            data = {
                'init_hooks': self.post_init_hooks[env] + self.post_init_hooks['shared'],
                'anot_hooks': self.anot_init_hooks[env] + self.anot_init_hooks['shared'],
                'annotations': self.anot_entries[env] + self.anot_init_hooks['shared']
            }
            converted = convert_dict(LuaPathResolver(ctx.workspace), data, prefix = 'local manifest =')
            out = template.replace('--manifest', converted)

            ctx.create_file(env, f'AnnotationInit.{env}.lua', out)


def load(ctx: AnnotationRegistry):
    ctx.registerExtension(ManifestExtension())