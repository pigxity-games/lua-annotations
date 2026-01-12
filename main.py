import argparse
from pathlib import Path
import json

#argument parsing
parser = argparse.ArgumentParser(prog='lua-annotations build-time processor/validator')
parser.add_argument('workdir', nargs='?', default='', help='working directory for the program; this should be your rojo project root')
parser.add_argument('-c', '--config', default='annotations.config.json', help='filename of the config file to use')
args = parser.parse_args()

#argument setup / assertion
workdir: Path = Path.cwd() / args.workdir
assert workdir.exists(), "workdir does not exist!"

config_file: Path = workdir / args.config
assert config_file.exists(), "config file not found!"

config = json.loads(config_file.read_text())