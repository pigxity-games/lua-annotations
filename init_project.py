from pathlib import Path
from annotations import AnnotationRegistry
from build_process import BuildProcessCtx, Environment
from parser import default_extension

DEFAULT_CONFIG = Path('./templates/annotations.config.json')

def create_config(workdir: Path, config_file: Path):
    if not config_file.exists():
        DEFAULT_CONFIG.copy_into(workdir)
        print('Created a default config file')
    else:
        print('Config file already exists. Skipping')

def build(workdir: Path, workspaces: dict[Environment, str]):
    reg = AnnotationRegistry()
    default_extension.load(reg)

    for env, path in workspaces.values():
        if env in ['client', 'server', 'shared']:
            ctx = BuildProcessCtx(reg, workdir / Path(path), env)
            ctx.process_dir()

    #TODO: post-process using another ctx class
    #for hook in reg.post_build_hooks:
    #    hook(ctx)