from pathlib import Path

from lua_annotations.api.annotations import SortedRegistry
from lua_annotations.api.lua_dict import LuaPath, LuaPathResolver, convert_dict
from lua_annotations.api.manifest import ManifestData, ManifestHook, ManifestHooks, ManifestModuleEntry, ManifestRemotes, RemoteEntry
from lua_annotations.build_process import PostProcessCtx
from lua_annotations.extensions.default import ManifestExtension

from helpers import extract_block, make_build_ctxs, make_workspace


def test_manifest_extension_generates_module_paths_with_clean_lua_paths(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    build_ctxs = make_build_ctxs(tmp_path, workspace)
    post_ctx = PostProcessCtx(SortedRegistry([], [], {}), tmp_path, workspace, build_ctxs)

    ext = ManifestExtension()
    shared_path = LuaPath(
        tmp_path / 'shared' / 'Generated' / '_Internal' / 'Lifecycle.lua',
        require=True,
        cache=True,
        properties=['remote'],
        cache_name='Lifecycle',
    )
    client_path = LuaPath(tmp_path / 'client' / 'Handlers' / 'NpcAnimation.lua', require=True, cache=True, cache_name='NpcAnimation')

    ext.add_annotation_handler('shared', 'remote', shared_path)
    ext.set_module_data(
        'client',
        'NpcAnimation',
        client_path,
        {
            'kind': 'module',
        },
    )

    ext.on_post_process(post_ctx)

    out = (tmp_path / 'client' / 'Generated' / 'Manifest.lua').read_text()
    module_paths_block = extract_block(out, 'modulePaths = {', 'manifest = {')

    assert 'Lifecycle = {ReplicatedStorage, "Generated", "_Internal", "Lifecycle"}' in module_paths_block
    assert 'NpcAnimation = {PlayerScripts, "Handlers", "NpcAnimation"}' in module_paths_block
    assert '..' not in module_paths_block


def test_manifest_extension_merges_shared_without_mutating_source(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    build_ctxs = make_build_ctxs(tmp_path, workspace)
    post_ctx = PostProcessCtx(SortedRegistry([], [], {}), tmp_path, workspace, build_ctxs)

    ext = ManifestExtension()
    shared_path = LuaPath(
        tmp_path / 'shared' / 'Generated' / '_Internal' / 'Lifecycle.lua',
        require=True,
        cache=True,
        properties=['initService'],
        cache_name='Lifecycle',
    )
    ext.register_hook('shared', 'module_handlers', shared_path)

    ext.on_post_process(post_ctx)

    assert ext.manifest['shared'].hooks.module_handlers[0].module == 'Lifecycle'
    assert ext.manifest['client'].hooks.module_handlers == []
    assert ext.manifest['server'].hooks.module_handlers == []

    out = (tmp_path / 'client' / 'Generated' / 'Manifest.lua').read_text()
    assert 'ManifestAPI.new({' in out
    assert 'manifest = {' in out
    assert 'hooks = {' in out
    assert 'annotation_handlers = {' in out
    assert 'module_handlers = {' in out
    assert 'post_init = {' in out


def test_manifest_models_serialize_runtime_shape(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    resolver = LuaPathResolver(workspace)

    hook_path = LuaPath(
        tmp_path / 'shared' / 'Generated' / '_Internal' / 'Lifecycle.lua',
        require=True,
        cache=True,
        properties=['initService'],
        cache_name='Lifecycle',
    )

    data = ManifestData(
        hooks=ManifestHooks(
            module_handlers=[ManifestHook(module='Lifecycle', method='initService', module_path=hook_path)]
        ),
        modules={
            'MessageController': ManifestModuleEntry(
                module_path=LuaPath(
                    tmp_path / 'client' / 'MessageController.lua',
                    require=True,
                    cache=True,
                    cache_name='MessageController',
                ),
                annotations={
                    'sendInfo': [
                        {
                            'name': 'remote',
                        }
                    ]
                },
            )
        },
        remotes=ManifestRemotes(
            client={
                'MessageController': {
                    'sendInfo': RemoteEntry(
                        service='MessageController',
                        method='sendInfo',
                        remoteType='event',
                    )
                }
            },
            server={},
        ),
    )

    data.register_module_paths(resolver)
    out = convert_dict(resolver, data, prefix='m.manifest =', include_imports=False)

    assert 'modules = {' in out
    assert 'MessageController = {' in out
    assert 'module_handlers = {' in out
    assert 'remotes = {' in out
    assert 'shared = {' not in out
    assert 'remoteType = "event"' in out
    assert 'getAdornee' not in out


def test_manifest_extension_registers_function_appends(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    build_ctxs = make_build_ctxs(tmp_path, workspace)
    post_ctx = PostProcessCtx(SortedRegistry([], [], {}), tmp_path, workspace, build_ctxs)

    ext = ManifestExtension()
    ext.register_manifest_functions('shared', 'function ManifestAPI.sharedFn()\nend')
    ext.register_manifest_functions('client', 'function ManifestAPI.clientFn()\nend')

    ext.on_post_process(post_ctx)

    client_out = (tmp_path / 'client' / 'Generated' / 'Manifest.lua').read_text()
    server_out = (tmp_path / 'server' / 'Generated' / 'Manifest.lua').read_text()
    manifest_api_out = (tmp_path / 'shared' / 'Generated' / '_Internal' / 'ManifestAPI.lua').read_text()

    assert 'function ManifestAPI.sharedFn()' not in client_out
    assert 'function ManifestAPI.clientFn()' not in client_out
    assert 'function ManifestAPI.sharedFn()' not in server_out
    assert 'function ManifestAPI.clientFn()' not in server_out
    assert 'function ManifestAPI.sharedFn()' in manifest_api_out
    assert 'function ManifestAPI.clientFn()' in manifest_api_out


def test_manifest_extension_merges_module_and_annotation_data(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    ext = ManifestExtension()

    module_path = LuaPath(tmp_path / 'server' / 'MyService.lua', require=True, cache=True, cache_name='MyService')
    ext.update_module_data('server', 'MyService', module_path, {'base': {'a': 1}})
    ext.update_module_data('server', 'MyService', module_path, {'base': {'b': 2}, 'extra': True})

    class DummyAnnotation:
        def __init__(self):
            self.export_data = {'base': {'x': 1}}

    annotation = DummyAnnotation()
    ext.update_annotation_data(annotation, {'base': {'y': 2}, 'flag': True})

    assert ext.manifest['server'].modules['MyService'].data == {
        'base': {'a': 1, 'b': 2},
        'extra': True,
    }
    assert annotation.export_data == {
        'base': {'x': 1, 'y': 2},
        'flag': True,
    }
