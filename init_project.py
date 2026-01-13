from pathlib import Path

DEFAULT_CONFIG = Path('./templates/annotations.config.json')

def create_config(workdir: Path, config_file: Path):
    if not config_file.exists():
        DEFAULT_CONFIG.copy_into(workdir)
        print('Created a default config file')
    else:
        print('Config file already exists. Skipping')