import argparse
from pathlib import Path
import sys
from typing import Literal

from .exceptions import LuaAnnotationsError
from .init_project import build, create_config, read_config, watch


def main():
    parser = argparse.ArgumentParser(prog='lua-anot')
    parser.add_argument('mode', help='mode of the program', choices=['build', 'init', 'watch'])
    parser.add_argument(
        'workdir',
        nargs='?',
        default='',
        help='working directory for the program; this should be your rojo project root',
    )
    parser.add_argument(
        '-c',
        '--config',
        default='annotations.config.json',
        help='filename of the config file to use',
    )
    parser.add_argument(
        '--watch-interval',
        type=float,
        default=1.0,
        help='polling interval in seconds when mode is watch',
    )
    args = parser.parse_args()

    mode: Literal['build', 'init', 'watch'] = args.mode

    workdir: Path = Path.cwd() / args.workdir
    if not workdir.exists() or not workdir.is_dir():
        raise LuaAnnotationsError(f'Invalid workdir: {workdir}. Provide a valid project directory.')

    config_file: Path = workdir / args.config

    # init mode
    if mode == 'init':
        create_config(workdir, config_file)
        return

    # main mode
    if mode == 'build':
        build(workdir, read_config(config_file))
        return

    # watch mode
    watch(workdir, config_file, poll_interval=args.watch_interval)

    return 0


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped watching.')
    except LuaAnnotationsError as exc:
        print(f'Error: {exc}')
        sys.exit(1)
