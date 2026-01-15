import argparse
from pathlib import Path
import json
from typing import Literal

from dir_scan import build
from init_project import create_config

#argument parsing
parser = argparse.ArgumentParser(prog='lua-annotations build-time processor/validator')
parser.add_argument('mode', help='mode of the program', choices=['build', 'init', 'watch'])
parser.add_argument('workdir', nargs='?', default='', help='working directory for the program; this should be your rojo project root')
parser.add_argument('-c', '--config', default='annotations.config.json', help='filename of the config file to use')
args = parser.parse_args()

#argument setup / assertion
mode: Literal['build', 'init', 'watch'] = args.mode

workdir: Path = Path.cwd() / args.workdir
assert workdir.exists() and workdir.is_dir(), "Specified workdir path is not a directory!"

config_file: Path = workdir / args.config
if mode == 'init':
    create_config(workdir, config_file)
    exit()

assert config_file.exists(), "Config file not found. Run the program in init mode to create one!"
config = json.loads(config_file.read_text())

# main mode
if mode == 'build':
    build(workdir)

#TODO: watch mode