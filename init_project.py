import importlib
from pathlib import Path
import shutil
import sys
import time
from datetime import datetime
from api.annotations import ENVIRONMENTS, AnnotationRegistry
from build_process import BuildCtxList, BuildProcessCtx, Config, Extension, PostProcessCtx

DEFAULT_CONFIG = Path('./templates/annotations.config.json')
WATCH_FILENAMES = ('*.lua', '*.luau')

def create_config(workdir: Path, config_file: Path):
    if not config_file.exists():
        shutil.copyfile(DEFAULT_CONFIG, config_file)
        print('Created a default config file')
    else:
        print('Config file already exists. Skipping')


def get_root_path(paths: dict[Path, str], env: str):
    root = next((p for p, expr in paths.items() if expr == ':'), None)
    if root is None:
        raise ValueError(f'environment `{env}` does not have a root path.')
    return root

def iter_rel_paths(path_map: dict[Path, str], workdir: Path):
    for path, lua_expr in path_map.items():
        p = workdir / path
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

    if entry_type == 'library':
        return importlib.import_module(entry)
    else:
        return import_extension_from_path(workdir, entry)


def build(workdir: Path, config: Config):
    init_time = datetime.now()

    for workspace in config.workspaces:
        reg = AnnotationRegistry()
        
        #load extensions
        for ext in config.extensions:
            module = import_extension(ext, workdir)
            load_fn = getattr(module, 'load')
            
            if callable(load_fn):
                load_fn(reg)
            else:
                raise ValueError(f'module {ext["py_entry"][1]} does not have a `load()` function')

            #TODO: store lua_entry paths somewhere

        print(f'loaded {len(reg.registry)} annotations')

        build_contexts: BuildCtxList = {}

        for env in ENVIRONMENTS:
            path_map = workspace.get(env)
            if not path_map:
                raise ValueError(f'path for the `{env}` environment is not defined in the config.')

            #convert each path to be relative to the workdir
            rel_paths = dict(iter_rel_paths(path_map, workdir))
        
            #process output root
            root_path = get_root_path(rel_paths, env)
            output_root = root_path / Path(config.out_dir_name)

            shutil.rmtree(output_root)
            output_root.mkdir(parents=True, exist_ok=True)

            #create a ctx
            ctx = BuildProcessCtx(reg, root_path, workspace, rel_paths, output_root, env)
            for path in rel_paths:
                ctx.process_dir(path)

            build_contexts[env] = ctx

        if not build_contexts:
            return

        # run post-build hooks
        ctx = PostProcessCtx(reg, workdir, workspace, build_contexts)
        for hook in reg.post_build_hooks:
            hook(ctx)

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
            rel_path = workspace.get(env)
            if not rel_path:
                continue

            env_workdir = workdir / Path(rel_path)
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

    assert config_file.exists(), 'Config file not found. Run the program in init mode to create one!'
    return Config(json.loads(config_file.read_text()))