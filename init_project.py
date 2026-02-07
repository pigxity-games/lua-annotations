from pathlib import Path
from typing import Any, cast
from annotations import AnnotationRegistry
from build_process import BuildCtxList, BuildProcessCtx, Environment, PostProcessCtx
from parser import default_extension

DEFAULT_CONFIG = Path('./templates/annotations.config.json')
ENVIRONMENTS = ['client', 'server', 'shared']

def create_config(workdir: Path, config_file: Path):
    if not config_file.exists():
        DEFAULT_CONFIG.copy_into(workdir)
        print('Created a default config file')
    else:
        print('Config file already exists. Skipping')


def build(workdir: Path, config: dict[Any, Any]):
    reg = AnnotationRegistry()
    default_extension.load(reg)

    output_dir_name = config.get('outDirName', 'Generated')
    workspaces: list[Any] = config.get('workspaces', [])

    build_contexts: BuildCtxList = {}
    build_state: dict[str, Any] = {}

    for workspace in workspaces:
        for env in ENVIRONMENTS:
            env = cast(Environment, env)

            path = workspace.get(env)
            if not path:
                continue

            env_workdir = workdir / Path(path)
            if not env_workdir.exists() or not env_workdir.is_dir():
                continue

            output_root = env_workdir / Path(output_dir_name)
            output_root.mkdir(exist_ok=True)

            ctx = BuildProcessCtx(reg, env_workdir, build_state, output_root, env)
            ctx.process_dir()
            build_contexts[env] = ctx

    if not build_contexts:
        return

    # run post-build hooks
    ctx = PostProcessCtx(reg, workdir, build_state, build_contexts)
    for hook in reg.post_build_hooks:
        hook(ctx)
