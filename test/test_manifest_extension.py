from pathlib import Path

from lua_annotations.api.annotations import SortedRegistry
from lua_annotations.api.lua_dict import LuaPath
from lua_annotations.api.manifest import ManifestAnnotation, ManifestData, ManifestHooks, ManifestMethod, ManifestModule
from lua_annotations.api.lua_dict import LuaPathResolver, convert_dict
from lua_annotations.build_process import PostProcessCtx
from lua_annotations.extensions.default import ManifestExtension

from helpers import extract_block, make_build_ctxs, make_workspace


def test_manifest_extension_generates_module_paths_with_clean_lua_paths(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    build_ctxs = make_build_ctxs(tmp_path, workspace)
    post_ctx = PostProcessCtx(SortedRegistry([], [], {}), tmp_path, workspace, build_ctxs)

    ext = ManifestExtension()
    ext.add_pre_init_hook(
        'shared',
        ManifestMethod(LuaPath(tmp_path / 'shared' / 'Generated' / '_Internal' / 'Lifecycle.lua', require=True, cache=True), 'setup'),
    )
    ext.add_pre_init_hook(
        'client',
        ManifestMethod(LuaPath(tmp_path / 'client' / 'Handlers' / 'NpcAnimation.lua', require=True, cache=True), 'setup'),
    )

    ext.on_post_process(post_ctx)

    out_file = tmp_path / 'client' / 'Generated' / 'Manifest.lua'
    out = out_file.read_text()

    module_paths_block = extract_block(out, 'm.paths = {', 'm.manifest = {')

    assert 'Lifecycle = {ReplicatedStorage, "Generated", "_Internal", "Lifecycle"}' in module_paths_block
    assert 'NpcAnimation = {PlayerScripts, "Handlers", "NpcAnimation"}' in module_paths_block
    assert '..' not in module_paths_block
    assert 'require(' not in module_paths_block
    assert 'module = "Lifecycle"' in out
    assert 'module = "NpcAnimation"' in out


def test_manifest_extension_merges_shared_without_mutating_source(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    build_ctxs = make_build_ctxs(tmp_path, workspace)
    post_ctx = PostProcessCtx(SortedRegistry([], [], {}), tmp_path, workspace, build_ctxs)

    ext = ManifestExtension()
    shared_path = LuaPath(tmp_path / 'shared' / 'Generated' / '_Internal' / 'Lifecycle.lua', require=True, cache=True)
    ext.add_pre_init_hook('shared', ManifestMethod(shared_path, 'setup'))
    ext.add_annotation_handler('shared', 'example', ManifestMethod(shared_path, 'example'))

    ext.on_post_process(post_ctx)

    assert ext.manifest['shared'].hooks.pre_init[0].module == 'Lifecycle'
    assert ext.manifest['client'].hooks.pre_init == []
    assert ext.manifest['server'].hooks.pre_init == []

    out = (tmp_path / 'client' / 'Generated' / 'Manifest.lua').read_text()
    assert 'hooks = {' in out
    assert 'annotation_handlers = {' in out
    assert 'pre_init = {' in out
    assert 'module_handlers = {' in out
    assert 'post_init = {' in out
    assert 'anot_hooks' not in out
    assert 'init_hooks' not in out


def test_manifest_template_includes_core_annotation_api_without_game_framework(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    build_ctxs = make_build_ctxs(tmp_path, workspace)
    post_ctx = PostProcessCtx(SortedRegistry([], [], {}), tmp_path, workspace, build_ctxs)

    ext = ManifestExtension()
    ext.on_post_process(post_ctx)

    out = (tmp_path / 'client' / 'Generated' / 'Manifest.lua').read_text()

    assert 'function m.getModuleData(moduleName)' in out
    assert 'function m.getAnnotationData(moduleName, methodName)' in out
    assert 'function m.getAnnotationAdornee(moduleName, methodName)' in out
    assert 'function m.setAnnotationHandler(name, handler)' in out
    assert 'function m.clearAnnotationHandler(name)' in out
    assert 'function m.runModuleAnnotations(moduleName, options)' in out
    assert 'function m.runAllAnnotations(options)' in out
    assert 'function m.getServiceData(serviceName)' not in out
    assert 'function m.callRemote(serviceName, methodName, options, ...)' not in out


def test_annotation_init_runs_module_handlers_without_load_order():
    template = Path('src/lua_annotations/templates/AnnotationInit.lua').read_text()

    assert 'if #data.load_order > 0 then' in template
    assert 'for _, moduleName in ipairs(data.load_order) do' in template
    assert 'else' in template
    assert 'for moduleName, module in pairs(data.modules) do' in template
    assert 'runModuleHandlers(module.data, moduleName)' in template


def test_manifest_models_serialize_runtime_shape(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    resolver = LuaPathResolver(workspace)

    data = ManifestData(
        hooks=ManifestHooks(pre_init=['initHook']),
        modules={
            'MessageController': ManifestModule(
                path=LuaPath(tmp_path / 'client' / 'MessageController.lua', require=True, cache=True),
                annotations={
                    'sendInfo': ManifestAnnotation(
                        name='remote',
                        args=['event'],
                        kwargs={},
                        data={'remote_env': 'client'},
                    )
                },
            )
        },
    )

    out = convert_dict(resolver, data, prefix='local manifest =', include_imports=False)

    assert 'hooks = {' in out
    assert 'modules = {' in out
    assert 'MessageController = {' in out
    assert 'shared = {' not in out
    assert 'remote_env = "client"' in out
