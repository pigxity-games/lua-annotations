from lua_annotations.api.annotations import (
    ENVIRONMENTS,
    AnnotationBuildCtx,
    AnnotationDef,
    ExtensionRegistry,
    Extension,
    FileBuildCtx,
)
from lua_annotations.api.manifest import ManifestData, ManifestMap, ManifestRemotes, ManifestServices, ServiceEntry
from lua_annotations.build_process import Environment, PostProcessCtx, get_template
from lua_annotations.parser_schemas import LuaMethod
from lua_annotations.api.lua_dict import LuaPathResolver, convert_dict


class ManifestExtension(Extension):
    def __init__(self):
        self.manifest: ManifestMap = {env: ManifestData() for env in ENVIRONMENTS}

    def add_init_hook(self, env: Environment, path):
        self.manifest[env].hooks.init.append(path)

    def add_post_init_hook(self, env: Environment, path):
        self.manifest[env].hooks.post_init.append(path)

    def add_annotation_handler(self, env: Environment, name: str, path):
        self.manifest[env].hooks.annotation_handlers[name] = path

    def add_runtime_annotation(self, env: Environment, annotation):
        self.manifest[env].annotations.append(annotation)

    def set_services(self, env: Environment, entries: dict[str, ServiceEntry], load_order: list[str]):
        self.manifest[env].services = ManifestServices(entries, load_order)

    def set_remotes(self, remotes: ManifestRemotes):
        for env in ('server', 'client'):
            self.manifest[env].remotes = remotes

    def on_build_post_init(self, ctx: AnnotationBuildCtx, key: str):
        adornee = ctx.annotation.adornee
        assert isinstance(adornee, LuaMethod)

        path = adornee.get_path(require=True, cache=True)
        if key == 'init':
            self.add_init_hook(ctx.build_ctx.env, path)
        else:
            self.add_post_init_hook(ctx.build_ctx.env, path)

    def on_build_annotation_init(self, ctx: AnnotationBuildCtx):
        adornee = ctx.annotation.adornee
        assert isinstance(adornee, LuaMethod)

        self.add_annotation_handler(ctx.build_ctx.env, ctx.annotation.adornee.name, adornee.get_path(require=True, cache=True))

    def load(self, ctx: ExtensionRegistry):
        ctx.register_anot(
            AnnotationDef(
                name='onInit',
                scope='method',
                on_build=lambda ctx: self.on_build_post_init(ctx, 'init'),
            )
        )
        ctx.register_anot(
            AnnotationDef(
                'onPostInit',
                scope='method',
                on_build=lambda ctx: self.on_build_post_init(ctx, 'post_init'),
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
                self.add_runtime_annotation(ctx.build_ctx.env, anot)

    def on_post_process(self, ctx: PostProcessCtx):
        for env in ('server', 'client'):
            template = get_template('AnnotationInit.lua')

            data = self.manifest[env].merged_with_shared(self.manifest['shared'])
            resolver = LuaPathResolver(ctx.workspace)

            converted = convert_dict(resolver, data, prefix='local manifest =', include_imports=False)
            module_paths = convert_dict(resolver, resolver.get_cached_module_paths(), prefix='local modulePaths =')
            out = template.replace(f'(env)', env).replace('--modulePaths', module_paths).replace('--manifest', converted)

            ctx.create_file(env, f'AnnotationInit.{env}.lua', out)


def load(ctx: ExtensionRegistry):
    ctx.register_extension(ManifestExtension())
