from lua_annotations.api.annotations import (
    ENVIRONMENTS,
    AnnotationBuildCtx,
    AnnotationDef,
    ExtensionRegistry,
    Extension,
    FileBuildCtx,
)
from lua_annotations.api.manifest import (
    ManifestAnnotation,
    ManifestData,
    ManifestMap,
    ManifestMethod,
    ManifestMethodRef,
    ManifestModule,
    merge_dicts,
)
from lua_annotations.build_process import Environment, PostProcessCtx, get_template
from lua_annotations.parser_schemas import LuaMethod
from lua_annotations.api.lua_dict import LuaPath, LuaPathResolver, convert_dict


class ManifestExtension(Extension):
    def __init__(self):
        self.manifest: ManifestMap = {env: ManifestData() for env in ENVIRONMENTS}
        self.method_appends: dict[Environment, list[str]] = {env: [] for env in ENVIRONMENTS}

    def _module_name_from_path(self, path):
        if isinstance(path, LuaPath):
            return path.path.with_suffix('').name

        return path.with_suffix('').name

    def _method_ref(self, env: Environment, method: ManifestMethod):
        self.add_module(env, self._module_name_from_path(method.path), method.path)
        return ManifestMethodRef(self._module_name_from_path(method.path), method.method)

    def add_pre_init_hook(self, env: Environment, method: ManifestMethod):
        self.manifest[env].hooks.pre_init.append(self._method_ref(env, method))

    def add_init_hook(self, env: Environment, path):
        self.add_pre_init_hook(env, ManifestMethod.from_path(path, self._module_name_from_path(path)))

    def add_post_init_hook(self, env: Environment, method: ManifestMethod):
        self.manifest[env].hooks.post_init.append(self._method_ref(env, method))

    def add_module_handler(self, env: Environment, method: ManifestMethod):
        self.manifest[env].hooks.module_handlers.append(self._method_ref(env, method))

    def add_annotation_handler(self, env: Environment, name: str, method: ManifestMethod):
        self.manifest[env].hooks.annotation_handlers[name] = self._method_ref(env, method)

    def add_module(self, env: Environment, name: str, path: LuaPath):
        self.manifest[env].modules.setdefault(name, ManifestModule(path))

    def add_module_data(self, env: Environment, name: str, path: LuaPath, data: dict):
        module = self.manifest[env].modules.setdefault(name, ManifestModule(path))
        merge_dicts(module.data, data)

    def add_runtime_annotation(self, env: Environment, annotation):
        module = annotation.get_module()
        if isinstance(annotation.adornee, LuaMethod):
            key = annotation.adornee.name
        else:
            key = '_module'

        self.add_module(env, module.returned_name, module.get_path(require=True, cache=True))
        self.manifest[env].modules[module.returned_name].annotations[key] = ManifestAnnotation(
            name=annotation.name,
            args=annotation.args_val,
            kwargs=annotation.kwargs_val,
            data=annotation.export_data,
        )

    def set_load_order(self, env: Environment, load_order: list[str]):
        self.manifest[env].load_order = load_order

    def add_methods(self, env: Environment, methods: str):
        self.method_appends[env].append(methods.strip())

    def on_build_post_init(self, ctx: AnnotationBuildCtx, key: str):
        adornee = ctx.annotation.adornee
        assert isinstance(adornee, LuaMethod)

        path = adornee.get_path(require=True, cache=True)
        method = ManifestMethod(path, adornee.name)
        if key == 'init':
            self.add_pre_init_hook(ctx.build_ctx.env, method)
        else:
            self.add_post_init_hook(ctx.build_ctx.env, method)

    def on_build_annotation_init(self, ctx: AnnotationBuildCtx):
        adornee = ctx.annotation.adornee
        assert isinstance(adornee, LuaMethod)

        self.add_annotation_handler(
            ctx.build_ctx.env,
            ctx.annotation.adornee.name,
            ManifestMethod(adornee.get_path(require=True, cache=True), adornee.name),
        )

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
            init_template = get_template('AnnotationInit.lua')
            manifest_template = get_template('Manifest.lua')

            data = self.manifest[env].merged_with_shared(self.manifest['shared'])
            resolver = LuaPathResolver(ctx.workspace)

            manifest = convert_dict(resolver, data, prefix='m.manifest =', include_imports=False)

            for module in data.modules.values():
                module.path.to_lua(resolver)

            paths = convert_dict(resolver, resolver.get_cached_module_paths(), prefix='m.paths =')
            method_appends = '\n\n'.join(self.method_appends['shared'] + self.method_appends[env])
            manifest_out = manifest_template.replace('--{paths}', paths).replace('--{manifest}', manifest).replace('--{method_appends}', method_appends)

            ctx.create_file(env, 'Manifest.lua', manifest_out)
            ctx.create_file(env, f'AnnotationInit.{env}.lua', init_template.replace('{env}', env))


def load(ctx: ExtensionRegistry):
    ctx.register_extension(ManifestExtension())
