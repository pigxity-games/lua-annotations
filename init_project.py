from pathlib import Path
import shutil
import time
from datetime import datetime
from api.annotations import ENVIRONMENTS, AnnotationRegistry
from build_process import BuildCtxList, BuildProcessCtx, Config, PostProcessCtx
from parser import default_extension

DEFAULT_CONFIG = Path('./templates/annotations.config.json')
WATCH_FILENAMES = ('*.lua', '*.luau')

def create_config(workdir: Path, config_file: Path):
    if not config_file.exists():
        shutil.copyfile(DEFAULT_CONFIG, config_file)
        print('Created a default config file')
    else:
        print('Config file already exists. Skipping')


def build(workdir: Path, config: Config):
    init_time = datetime.now()

    for workspace in config.workspaces:
        reg = AnnotationRegistry()
        default_extension.load(reg)

        build_contexts: BuildCtxList = {}

        for env in ENVIRONMENTS:
            path = workspace.get(env)
            if not path:
                raise ValueError(f'path for the `{env}` environment is not defined in the config.')

            env_workdir = workdir / Path(path)
            if not env_workdir.exists() or not env_workdir.is_dir():
                continue

            output_root = env_workdir / Path(config.out_dir_name)

            shutil.rmtree(output_root)
            output_root.mkdir(parents=True, exist_ok=True)

            ctx = BuildProcessCtx(reg, env_workdir, workspace, output_root, env)
            ctx.process_dir()
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