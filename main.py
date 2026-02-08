import argparse
from pathlib import Path
from typing import Literal

from init_project import build, create_config, read_config, watch


def main() -> None:
    parser = argparse.ArgumentParser(prog='lua-annotations build-time processor/validator')
    parser.add_argument('mode', help='mode of the program', choices=['build', 'init', 'watch'])
    parser.add_argument(
        'workdir',
        nargs='?',
        default='',
        help='working directory for the program; this should be your rojo project root',
    )
    parser.add_argument('-c', '--config', default='annotations.config.json', help='filename of the config file to use')
    parser.add_argument(
        '--watch-interval',
        type=float,
        default=1.0,
        help='polling interval in seconds when mode is watch',
    )
    args = parser.parse_args()

    mode: Literal['build', 'init', 'watch'] = args.mode

    workdir: Path = Path.cwd() / args.workdir
    assert workdir.exists() and workdir.is_dir(), 'Specified workdir path is not a directory!'

    config_file: Path = workdir / args.config

    #init mode
    if mode == 'init':
        create_config(workdir, config_file)
        return

    #main mode
    if mode == 'build':
        build(workdir, read_config(config_file))
        return

    #watch mode
    try:
        watch(workdir, config_file, poll_interval=args.watch_interval)
    except KeyboardInterrupt:
        print('\nStopped watching.')

if __name__ == '__main__':
    main()