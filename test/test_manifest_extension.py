from pathlib import Path

from lua_annotations.api.annotations import SortedRegistry
from lua_annotations.api.lua_dict import LuaPath
from lua_annotations.api.manifest import ManifestData, ManifestHooks, ManifestRemotes, RemoteEntry
from lua_annotations.api.lua_dict import LuaPathResolver, convert_dict
from lua_annotations.build_process import PostProcessCtx
from lua_annotations.config import Config
from lua_annotations.extensions.default import ManifestExtension

from helpers import extract_block, make_build_ctxs, make_workspace


def test_manifest_extension_generates_module_paths_with_clean_lua_paths(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    build_ctxs = make_build_ctxs(tmp_path, workspace)
    post_ctx = PostProcessCtx(SortedRegistry([], [], {}), tmp_path, workspace, Config(out_dir_name='Generated'), 'test', build_ctxs)

    ext = ManifestExtension()
    ext.add_init_hook('shared', LuaPath(tmp_path / 'shared' / 'Generated' / '_Internal' / 'Lifecycle.lua', require=True, cache=True))
    ext.add_init_hook('client', LuaPath(tmp_path / 'client' / 'Handlers' / 'NpcAnimation.lua', require=True, cache=True))

    ext.on_post_process(post_ctx)

    out_file = tmp_path / 'client' / 'Generated' / 'AnnotationInit.client.lua'
    out = out_file.read_text()

    module_paths_block = extract_block(out, 'local modulePaths = {', 'local cache = {}')

    assert 'Lifecycle = {ReplicatedStorage, "Generated", "_Internal", "Lifecycle"}' in module_paths_block
    assert 'NpcAnimation = {PlayerScripts, "Handlers", "NpcAnimation"}' in module_paths_block
    assert '..' not in module_paths_block
    assert 'require(' not in module_paths_block
    assert 'getCached("Lifecycle")' in out
    assert 'getCached("NpcAnimation")' in out


def test_manifest_extension_merges_shared_without_mutating_source(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    build_ctxs = make_build_ctxs(tmp_path, workspace)
    post_ctx = PostProcessCtx(SortedRegistry([], [], {}), tmp_path, workspace, Config(out_dir_name='Generated'), 'test', build_ctxs)

    ext = ManifestExtension()
    shared_path = LuaPath(tmp_path / 'shared' / 'Generated' / '_Internal' / 'Lifecycle.lua', require=True, cache=True)
    ext.add_init_hook('shared', shared_path)
    ext.add_annotation_handler('shared', 'example', shared_path)

    ext.on_post_process(post_ctx)

    assert ext.manifest['shared'].hooks.init == [shared_path]
    assert ext.manifest['client'].hooks.init == []
    assert ext.manifest['server'].hooks.init == []

    out = (tmp_path / 'client' / 'Generated' / 'AnnotationInit.client.lua').read_text()
    assert 'hooks = {' in out
    assert 'annotation_handlers = {' in out
    assert 'init = {' in out
    assert 'post_init = {' in out
    assert 'anot_hooks' not in out
    assert 'init_hooks' not in out


def test_manifest_models_serialize_runtime_shape(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    resolver = LuaPathResolver(workspace)

    data = ManifestData(
        hooks=ManifestHooks(init=['initHook']),
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

    out = convert_dict(resolver, data, prefix='local manifest =', include_imports=False)

    assert 'hooks = {' in out
    assert 'remotes = {' in out
    assert 'client = {' in out
    assert 'server = {' in out
    assert 'shared = {' not in out
    assert 'remoteType = "event"' in out
