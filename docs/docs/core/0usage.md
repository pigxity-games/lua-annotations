# CLI Usage
The CLI tool can be ran with the following command:
```bash
lua-anot {mode} {args} {workdir: default = .}
```

## Modes
* `build`: builds the project under `workdir`.
* `watch`: watches for changes under `workdir`; if it detects any, the project is rebuilt.
* `init`: creates a default `annotations.config.json` file inside the `workdir`.

## Args
* `-c`/`--config`: path to the config file to use (default = 'annotations.config.json')
* `--watch-interval`: polling interval (in seconds) for watch mode.