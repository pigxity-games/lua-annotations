import importlib
from pathlib import Path
import shutil
import sys
import time
from datetime import datetime
from api.annotations import ENVIRONMENTS, ExtensionRegistry
from build_process import BuildCtxList, BuildProcessCtx, Config, Environment, Extension, LuaEntry, PostProcessCtx, Workspace
import lua_extension_anots
from exceptions import BuildError, ConfigError

DEFAULT_CONFIG = Path('./templates/annotations.config.json')
WATCH_FILENAMES = ('*.lua', '*.luau')

def create_config(workdir: Path, config_file: Path):
    if not config_file.exists():
        shutil.copyfile(DEFAULT_CONFIG, config_file)
        print('Created a default config file')
    else:
        print('Config file already exists. Skipping')


def iter_rel_paths(path_map: dict[str, str], workdir: Path):
    for path, lua_expr in path_map.items():
        p = workdir / Path(path)
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


def import_extension(ext: Extension, workdir: Path):
    entry_type, entry = ext['py_entry']

    try:
        if entry_type == 'library':
            return importlib.import_module(entry)
        return import_extension_from_path(workdir, entry)
    except ModuleNotFoundError as exc:
        raise BuildError(
            f'failed to import extension module {entry}.'
        ) from exc


def parse_lua_entry(entry: LuaEntry, env: Environment, workdir: Path):
    type, value = entry[env]
    raw_path, expr = value
    if not isinstance(raw_path, str) or not isinstance(expr, str):
        raise ConfigError(f'invalid lua_entry for {env}: expected path and expr strings')

    if type == 'wally':    
        package_dir_name = 'Packages' if env == 'shared' else 'ServerPackages'
        packages = workdir / package_dir_name / '_Index'
        ext_dir = next(packages.glob(f'*_{raw_path}@*'), None)
        if not ext_dir:
            raise ConfigError(
                f'wally package {raw_path} not found under {packages.as_posix()}'
            )

        return ext_dir / raw_path, expr

    elif type == 'path':
        return workdir / Path(raw_path), expr
    else:
        raise ConfigError('incorrect lua_entry type in the config file.')
    

def build(workdir: Path, config: Config):
    init_time = datetime.now()

    for raw_workspace in config.workspaces:
        #process workspace
        workspace: Workspace = {}
        for env in ENVIRONMENTS:
            path_map = raw_workspace.get(env)
            if not path_map:
                raise ConfigError(f'path for the `{env}` environment is not defined in the config.')

            rel_paths = dict(iter_rel_paths(path_map, workdir))
            workspace[env] = rel_paths


        #load extensions
        reg = ExtensionRegistry()
        lua_extension_anots.load(reg)

        for ext in config.extensions:
            #py_entry
            module = import_extension(ext, workdir)
            load_fn = getattr(module, 'load')

            if not callable(load_fn):
                raise BuildError(f'module {ext["py_entry"][1]} does not have a `load()` function')
            load_fn(reg)

            #process lua_entry, adding paths to workspace
            for env in ('server', 'shared'):
                if env not in ext['lua_entry']:
                    continue

                path, expr = parse_lua_entry(ext['lua_entry'], env, workdir)
                workspace[env][path] = expr


        reg = reg.sort_extensions()
        print(f'loaded {len(reg.anot_registry)} annotations')


        #env processing
        build_contexts: BuildCtxList = {}

        for env in ENVIRONMENTS:
            path_map = workspace.get(env)
            if not path_map:
                raise ConfigError(f'path for the `{env}` environment is not defined in the config.')

            #process output root
            rel_paths = workspace[env]
            root_path = next(iter(rel_paths.keys()))
            output_root = root_path / Path(config.out_dir_name)

            shutil.rmtree(output_root, True)
            output_root.mkdir(parents=True, exist_ok=True)

            #create and use a ctx
            ctx = BuildProcessCtx(reg, root_path, workspace, rel_paths, output_root, env)
            for path in rel_paths:
                ctx.process_dir(path)

            build_contexts[env] = ctx


        # run post-build hooks
        if build_contexts:
            ctx = PostProcessCtx(reg, workdir, workspace, build_contexts)
            for hook in reg.post_build_hooks:
                hook(ctx)

    #logging
    delta = datetime.now() - init_time
    print(f'Built in {delta.total_seconds()}s')


#builds a fingerprint of all the last modified times of files
def _watch_fingerprint(workdir: Path, config_file: Path, config: Config):
    output_dir_name = config.out_dir_name

    #track config file
    tracked: dict[str, int] = {str(config_file): config_file.stat().st_mtime_ns}

    #track workspaces
    for workspace in config.workspaces:
        for env in ENVIRONMENTS:
            path_map = workspace.get(env)
            if not path_map:
                continue

            for rel_path in path_map:
                env_workdir = workdir / rel_path
                if not env_workdir.exists() or not env_workdir.is_dir():
                    continue

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

    #poll fingerprints every `poll_interval` seconds
    while True:
        time.sleep(poll_interval)

        config = read_config(config_file)
        fingerprint = _watch_fingerprint(workdir, config_file, config)

        if fingerprint != last_fingerprint:
            print('Change detected, rebuilding...')
            build(workdir, config)
            last_fingerprint = fingerprint


def read_config(config_file: Path):
    import json

    if not config_file.exists():
        raise ConfigError('Config file not found. Run the program in init mode to create one!')
    return Config(json.loads(config_file.read_text()))