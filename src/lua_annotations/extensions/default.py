from pathlib import Path
from typing import Any, cast

from lua_annotations.api.annotations import (
    ENVIRONMENTS,
    AnnotationBuildCtx,
    AnnotationDef,
    ExtensionRegistry,
    Extension,
    FileBuildCtx,
)
from lua_annotations.api.lua_dict import LuaPath, LuaPathResolver, convert_dict
from lua_annotations.api.manifest import (
    HookPhase,
    ManifestData,
    ManifestHook,
    ManifestMap,
    ManifestModuleEntry,
    ManifestRemotes,
    merge_manifest_value,
)
from lua_annotations.build_process import Environment, PostProcessCtx, get_template
from lua_annotations.parser_schemas import Annotation, LuaMethod


class ManifestExtension(Extension):
    def __init__(self):
        self.manifest: ManifestMap = {env: ManifestData() for env in ENVIRONMENTS}
        self.function_appends: dict[Environment, list[str]] = {env: [] for env in ENVIRONMENTS}

    def _get_module_entry(self, env: Environment, module_name: str, module_path):
        entry = self.manifest[env].modules.get(module_name)
        if entry is None:
            entry = ManifestModuleEntry(module_path=module_path)
            self.manifest[env].modules[module_name] = entry

        return entry

    def _get_manifest_path(self, build_ctx, module, properties: list[str] | None = None):
        file = module.file
        cache_name = module.returned_name
        props = properties or []

        if build_ctx is None:
            return module.get_path(require=True, cache=True, properties=props, cache_name=cache_name)

        try:
            rel = file.relative_to(build_ctx.output_root)
        except ValueError:
            return module.get_path(require=True, cache=True, properties=props, cache_name=cache_name)

        prefixed = Path(build_ctx.env) / build_ctx.output_root.name / rel
        return LuaPath(prefixed, require=True, properties=props, cache=True, cache_name=cache_name)

    def register_hook(self, env: Environment, phase: HookPhase, path):
        module = path.path.with_suffix('').name
        hook = ManifestHook(module=module, method=path.properties[-1], module_path=path)
        getattr(self.manifest[env].hooks, phase).append(hook)

    def add_annotation_handler(self, env: Environment, name: str, path):
        module = path.path.with_suffix('').name
        self.manifest[env].hooks.annotation_handlers[name] = ManifestHook(
            module=module,
            method=path.properties[-1],
            module_path=path,
        )

    def add_runtime_annotation(self, build_ctx, annotation: Annotation):
        module = annotation.get_module()
        env = build_ctx.env
        module_name = module.returned_name  # pyright: ignore[reportAttributeAccessIssue]
        module_path = self._get_manifest_path(build_ctx, module)
        entry = self._get_module_entry(env, module_name, module_path)

        adornee = annotation.adornee
        method_name = adornee.name if isinstance(adornee, LuaMethod) else '_module'

        entry.annotations.setdefault(method_name, [])
        entry.annotations[method_name].append(annotation)

    def set_module_data(self, env: Environment, module_name: str, module_path, data):
        entry = self._get_module_entry(env, module_name, module_path)
        entry.data = data

    def update_module_data(self, env: Environment, module_name: str, module_path, data):
        entry = self._get_module_entry(env, module_name, module_path)
        entry.data = merge_manifest_value(entry.data, data)

    def update_annotation_data(self, annotation: Any, data: dict[object, object]):
        merged = merge_manifest_value(annotation.export_data, data)
        annotation.export_data = cast(dict[Any, Any], merged)

    def set_load_order(self, env: Environment, load_order: list[str]):
        self.manifest[env].load_order = load_order

    def register_manifest_functions(self, env: Environment, content: str):
        self.function_appends[env].append(content.strip())

    def set_remotes(self, remotes: ManifestRemotes):
        for env in ('server', 'client'):
            self.manifest[env].remotes = remotes

    def on_build_hook(self, ctx: AnnotationBuildCtx, phase: HookPhase):
        adornee = ctx.annotation.adornee
        assert isinstance(adornee, LuaMethod)

        path = self._get_manifest_path(ctx.build_ctx, adornee.module, [adornee.name])
        self.register_hook(ctx.build_ctx.env, phase, path)

    def on_build_annotation_init(self, ctx: AnnotationBuildCtx):
        adornee = ctx.annotation.adornee
        assert isinstance(adornee, LuaMethod)

        path = self._get_manifest_path(ctx.build_ctx, adornee.module, [adornee.name])
        self.add_annotation_handler(ctx.build_ctx.env, ctx.annotation.adornee.name, path)

    def load(self, ctx: ExtensionRegistry):
        ctx.register_anot(
            AnnotationDef(
                name='onInit',
                scope='method',
                on_build=lambda build_ctx: self.on_build_hook(build_ctx, 'pre_init'),
            )
        )
        ctx.register_anot(
            AnnotationDef(
                name='moduleInit',
                scope='method',
                on_build=lambda build_ctx: self.on_build_hook(build_ctx, 'module_handlers'),
            )
        )
        ctx.register_anot(
            AnnotationDef(
                'onPostInit',
                scope='method',
                on_build=lambda build_ctx: self.on_build_hook(build_ctx, 'post_init'),
            )
        )
        ctx.register_anot(
            AnnotationDef(
                name='annotationInit',
                scope='method',
                on_build=self.on_build_annotation_init,
            )
        )

        ctx.register_anot(AnnotationDef(name='module', scope='module'))

    def on_file_process(self, ctx: FileBuildCtx):
        for anot in ctx.parser.annotations:
            if anot.adef.retention != 'build':
                self.add_runtime_annotation(ctx.build_ctx, anot)

    def on_post_process(self, ctx: PostProcessCtx):
        manifest_template = get_template('Manifest.lua')
        manifest_api_template = get_template('ManifestAPI.lua')
        init_template = get_template('AnnotationInit.lua')

        function_blocks = self.function_appends['shared'] + self.function_appends['client'] + self.function_appends['server']
        function_appends = '\n\n'.join(block for block in function_blocks if block)
        manifest_api_out = manifest_api_template.replace('--{function_appends}', function_appends)
        ctx.create_file('shared', '_Internal/ManifestAPI.lua', manifest_api_out)

        for env in ('server', 'client'):
            resolver = LuaPathResolver(ctx.workspace)
            data = self.manifest[env].merged_with_shared(self.manifest['shared'])
            data.register_module_paths(resolver)

            manifest_data = convert_dict(resolver, data, prefix='\tmanifest =', include_imports=False).rstrip() + ',\n'
            import_lines = [line for line in resolver.get_import_lines() if not line.startswith('local ReplicatedStorage = ')]
            module_path_imports = '\n'.join(import_lines)
            if module_path_imports:
                module_path_imports = module_path_imports + '\n'

            module_paths = convert_dict(
                resolver,
                resolver.get_cached_module_paths(),
                prefix='\tmodulePaths =',
                include_imports=False,
            ).rstrip() + ',\n'
            out_dir_name = ctx.build_ctxs['shared'].output_root.name

            manifest_out = (
                manifest_template.replace('(env)', env)
                .replace('(out-dir-name)', out_dir_name)
                .replace('--{module_imports}', module_path_imports.rstrip())
                .replace('--{module_paths}', module_paths)
                .replace('--{manifest}', manifest_data)
            )

            ctx.create_file(env, 'Manifest.lua', manifest_out)

            env_root = 'game:GetService(\'ServerScriptService\')'
            if env == 'client':
                env_root = 'game:GetService(\'Players\').LocalPlayer.PlayerScripts'

            init_out = init_template.replace('(env-root)', env_root).replace('(env)', env)
            ctx.create_file(env, f'AnnotationInit.{env}.lua', init_out)


def load(ctx: ExtensionRegistry):
    ctx.register_extension(ManifestExtension())
