from pathlib import Path
from annotations import AnnotationRegistry
from build_process import BuildProcessCtx
from parser import default_extension

DEFAULT_CONFIG = Path('./templates/annotations.config.json')


def create_config(workdir: Path, config_file: Path):
    if not config_file.exists():
        DEFAULT_CONFIG.copy_into(workdir)
        print('Created a default config file')
    else:
        print('Config file already exists. Skipping')


def build(workdir: Path, config: dict):
    reg = AnnotationRegistry()
    default_extension.load(reg)

    output_root = workdir / config.get('outDirName', 'Generated')
    workspaces = config.get('workspaces', [])

    build_state = {}
    build_contexts: list[BuildProcessCtx] = []

    for workspace in workspaces:
        for env in ['client', 'server', 'shared']:
            path = workspace.get(env)
            if not path:
                continue

            env_workdir = workdir / Path(path)
            if not env_workdir.exists() or not env_workdir.is_dir():
                continue

            ctx = BuildProcessCtx(reg, env_workdir, env, output_root, build_state)
            ctx.process_dir()
            build_contexts.append(ctx)

    if not build_contexts:
        return

    # run post-build hooks once with a deterministic shared output context
    post_ctx = BuildProcessCtx(reg, workdir, 'shared', output_root, build_state)
    for hook in reg.post_build_hooks:
        hook(post_ctx)
