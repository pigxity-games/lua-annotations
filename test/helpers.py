from pathlib import Path

from lua_annotations.api.annotations import ENVIRONMENTS, SortedRegistry
from lua_annotations.api.lua_dict import LuaPathResolver
from lua_annotations.build_process import BuildProcessCtx, Workspace


def make_workspace(
    tmp_path: Path,
    server_expr: str = ':ServerRoot',
    client_expr: str = ':ClientRoot',
    shared_expr: str = ':SharedRoot',
) -> Workspace:
    workspace: Workspace = {
        'server': {tmp_path / 'server': server_expr},
        'client': {tmp_path / 'client': client_expr},
        'shared': {tmp_path / 'shared': shared_expr},
    }
    return workspace


def make_resolver(
    tmp_path: Path,
    server_expr: str = ':ServerRoot',
    client_expr: str = ':ClientRoot',
    shared_expr: str = ':SharedRoot',
):
    workspace = make_workspace(tmp_path, server_expr, client_expr, shared_expr)
    return LuaPathResolver(workspace)


def make_build_ctxs(tmp_path: Path, workspace: Workspace):
    reg = SortedRegistry([], [], {})
    out = {}

    for env in ENVIRONMENTS:
        root = tmp_path / env
        root.mkdir(parents=True, exist_ok=True)
        output_root = root / 'Generated'
        output_root.mkdir(parents=True, exist_ok=True)
        out[env] = BuildProcessCtx(reg, root, workspace, workspace[env], output_root, env)

    return out


def extract_block(text: str, start: str, end: str):
    start_idx = text.index(start)
    end_idx = text.index(end, start_idx)
    return text[start_idx:end_idx]
