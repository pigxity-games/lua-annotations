from pathlib import Path

from lua_annotations.api.annotations import SortedRegistry
from lua_annotations.api.lua_dict import LuaPath
from lua_annotations.build_process import PostProcessCtx
from lua_annotations.extensions.default import ManifestExtension

from helpers import extract_block, make_build_ctxs, make_workspace


def test_manifest_extension_generates_module_paths_with_clean_lua_paths(tmp_path: Path):
    workspace = make_workspace(tmp_path, server_expr=':.', client_expr=':.', shared_expr=':.')
    build_ctxs = make_build_ctxs(tmp_path, workspace)
    post_ctx = PostProcessCtx(SortedRegistry([], [], {}), tmp_path, workspace, build_ctxs)

    ext = ManifestExtension()
    ext.manifest['shared']['init_hooks'].append(
        LuaPath(tmp_path / 'shared' / 'Generated' / '_Internal' / 'Lifecycle.lua', require=True, cache=True)
    )
    ext.manifest['client']['init_hooks'].append(
        LuaPath(tmp_path / 'client' / 'Handlers' / 'NpcAnimation.lua', require=True, cache=True)
    )

    ext.on_post_process(post_ctx)

    out_file = tmp_path / 'client' / 'Generated' / 'AnnotationInit.client.lua'
    out = out_file.read_text()

    module_paths_block = extract_block(out, 'local modulePaths = {', 'local cache = {}')

    assert 'Lifecycle = ReplicatedStorage.Generated._Internal.Lifecycle' in module_paths_block
    assert 'NpcAnimation = PlayerScripts.Handlers.NpcAnimation' in module_paths_block
    assert '..' not in module_paths_block
    assert 'require(' not in module_paths_block
    assert 'getCached("Lifecycle")' in out
    assert 'getCached("NpcAnimation")' in out
