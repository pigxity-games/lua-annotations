# CLI Usage
The CLI tool can be run with the following command:
```bash
lua-anot {mode} {args} {workdir: default = .}
```

## Modes
* `build`: builds the project under `workdir`.
* `watch`: watches for changes under `workdir`; if it detects any, the project is rebuilt.
* `init`: creates a default `annotations.config.json` file inside the `workdir`.

## Args
* `-c`/`--config`: path to the config file to use, relative to `workdir` (default = `annotations.config.json`)
* `-e`/`--extension`: optional extension name to enable. This may be repeated, for example `-e unit-test -e other-extension`, or set to `all` to enable every configured optional extension.
* `--watch-interval`: polling interval (in seconds) for watch mode.

## Generated files
Build mode deletes and recreates the generated directory for each environment root. By default this directory is named `Generated`.

The core extension creates runtime init files for the server and client. The game framework extension also creates files such as `Index.lua`, `ServiceTypes.lua`, `_Internal/Lifecycle.lua`, and `Remotes.model.json`.

!!! warning
    Do not edit files under `Generated` manually. They are replaced on each build.
