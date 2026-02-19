from api.annotations import ENVIRONMENTS, AnnotationBuildCtx, AnnotationDef, AnnotationRegistry, Extension
from build_process import Environment, PostProcessCtx
from parser_schemas import LuaMethod
from api.lua_dict import LuaPath, LuaPathResolver, convert_dict


type L = list[tuple[LuaPath, LuaMethod]]
type D = dict[Environment, L]

def on_build(dict: D, ctx: AnnotationBuildCtx):
    adornee = ctx.annotation.adornee
    assert isinstance(adornee, LuaMethod)

    dict[ctx.build_ctx.env].append((adornee.module.get_path(ctx.parser.file, require=True), adornee))

def process_data(list: L):
    return [f'{t[0]}.{t[1]}' for t in list]


class ManifestExt(Extension):
    def __init__(self):
        self.post_init_hooks: D = {env: [] for env in ENVIRONMENTS}
        self.anot_init_hooks: D = {env: [] for env in ENVIRONMENTS}

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

    def on_post_process(self, ctx: PostProcessCtx):
        for env in ('server', 'client'):
            with open('./templates/AnotInit.lua') as f:
                template = f.read()

            data = {
                'init_hooks': process_data(self.post_init_hooks[env]),
                'anot_hooks': process_data(self.anot_init_hooks[env])
            }
            converted = convert_dict(LuaPathResolver(ctx.workspace), data, prefix = 'local manifest =')
            print(converted)
            template.replace('--manifest', converted)
            
            ctx.create_file(env, f'AnotInit.{env}.lua', template)


def load(ctx: AnnotationRegistry):
    ctx.registerExtension(ManifestExt())