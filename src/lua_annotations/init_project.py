import importlib
from pathlib import Path
import shutil
import sys
import time
from datetime import datetime

from .api.annotations import ENVIRONMENTS, ExtensionRegistry
from .build_process import (
    BuildCtxList,
    BuildProcessCtx,
    Environment,
    PostProcessCtx,
    Workspace,
    get_template,
)
from .config import Config, ExtensionConfig, read_config
from .exceptions import BuildError, ConfigError
from .extensions import default as default_ext

WATCH_FILENAMES = ('*.lua', '*.luau')


def create_config(workdir: Path, config_file: Path):
    if not config_file.exists():
        default_config = get_template('annotations.config.json')
        config_file.write_text(default_config)
        print('Created a default config file')
    else:
        print('Config file already exists. Skipping')


def resolve_rel_path(path: str, lua_expr: str, workdir: Path, env: Environment):
    if '@' in path:
        return process_tags(path, lua_expr, env, workdir)
    return workdir / Path(path), lua_expr


def iter_rel_paths(path_map: dict[str, str], workdir: Path, env: Environment):
    for path, lua_expr in path_map.items():
        p, lua_expr = resolve_rel_path(path, lua_expr, workdir, env)

        if not p.is_dir():
            print(f'WARNING: directory {p.as_posix()} does not exist')
            continue

        yield p, lua_expr


def import_extension_from_path(workdir: Path, entry: str):
    workdir = workdir.resolve()
    p = (workdir / entry).resolve()

    if str(workdir) not in sys.path:
        sys.path.insert(0, str(workdir))
        importlib.invalidate_caches()

    mod_name = '.'.join(p.relative_to(workdir).with_suffix('').parts)
    return importlib.import_module(mod_name)


def import_extension(ext: ExtensionConfig, workdir: Path):
    if ext.kind == 'library':
        return importlib.import_module("lua_annotations.extensions.game_framework.main")
    return import_extension_from_path(workdir, ext.expr)


def process_tags(raw: str, raw_expr: str, env: Environment, workdir: Path):
    name, data = raw.split('@')

    if name == 'wally':
        package_dir_name = 'Packages' if env == 'shared' else 'ServerPackages'
        packages = workdir / package_dir_name / '_Index'
        ext_dir = next(packages.glob(f'*_{data}@*'), None)
        if not ext_dir:
            raise ConfigError(f'wally package {data} not found under {packages.as_posix()}')

        return ext_dir / data, f'require({raw_expr}["{data}"])'

    raise ConfigError(f'invalid path tag: {raw}')


def build(workdir: Path, config: Config):
    init_time = datetime.now()

    for workspace_cfg in config.workspaces:
        # process workspace
        workspace: Workspace = {}
        for env in ENVIRONMENTS:
            path_map = workspace_cfg.get(env)
            rel_paths = dict(iter_rel_paths(path_map, workdir, env))
            if not rel_paths:
                raise ConfigError(f'no valid directories were found for `{env}` in this workspace.')
            workspace[env] = rel_paths

        # load extensions
        reg = ExtensionRegistry()
        default_ext.load(reg)

        for ext in config.extensions:
            # py_entry
            module = import_extension(ext, workdir)
            load_fn = getattr(module, 'load')

            if not callable(load_fn):
                raise BuildError(f'module {ext.expr} does not have a `load()` function')
            load_fn(reg)

        reg = reg.sort_extensions()
        print(f'loaded {len(reg.anot_registry)} annotations')

        # env processing
        build_contexts: BuildCtxList = {}

        for env in ENVIRONMENTS:
            # process output root
            rel_paths = workspace[env]
            root_key = workspace_cfg.get_root(env)
            root_expr = workspace_cfg.get(env)[root_key]
            root_path, _ = resolve_rel_path(root_key, root_expr, workdir, env)
            if not root_path.is_dir():
                raise ConfigError(
                    f'root directory `{root_path.as_posix()}` does not exist for `{env}` in this workspace.'
                )
            output_root = root_path / Path(config.out_dir_name)

            shutil.rmtree(output_root, True)
            output_root.mkdir(parents=True, exist_ok=True)

            # create and use a ctx
            ctx = BuildProcessCtx(reg, root_path, workspace, rel_paths, output_root, env)
            for path in rel_paths:
                ctx.process_dir(path)

            build_contexts[env] = ctx

        # run post-build hooks
        if build_contexts:
            ctx = PostProcessCtx(reg, workdir, workspace, build_contexts)
            for hook in reg.post_build_hooks:
                hook(ctx)

    # logging
    delta = datetime.now() - init_time
    print(f'Built in {delta.total_seconds()}s')


# builds a fingerprint of all the last modified times of files
def _watch_fingerprint(workdir: Path, config_file: Path, config: Config):
    output_dir_name = config.out_dir_name

    # track config file
    tracked: dict[str, int] = {str(config_file): config_file.stat().st_mtime_ns}

    # track workspaces
    for workspace in config.workspaces:
        for env in ENVIRONMENTS:
            path_map = workspace.get(env)
            for env_workdir, _ in iter_rel_paths(path_map, workdir, env):
                for pattern in WATCH_FILENAMES:
                    for file in env_workdir.rglob(pattern):
                        if output_dir_name in file.parts:
                            continue
                        tracked[str(file)] = file.stat().st_mtime_ns

    return tuple(sorted(tracked.items()))


def watch(workdir: Path, config_file: Path, poll_interval: float = 1.0):
    print('Running initial build...')
    config = read_config(config_file)
    build(workdir, config)

    last_fingerprint = _watch_fingerprint(workdir, config_file, config)
    print(f'Watching for changes in {workdir} (interval: {poll_interval}s). Press Ctrl+C to stop.')

    # poll fingerprints every `poll_interval` seconds
    while True:
        time.sleep(poll_interval)

        config = read_config(config_file)
        fingerprint = _watch_fingerprint(workdir, config_file, config)

        if fingerprint != last_fingerprint:
            print('Change detected, rebuilding...')
            build(workdir, config)
            last_fingerprint = fingerprint
