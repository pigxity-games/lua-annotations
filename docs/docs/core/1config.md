# Config format
This is a rundown of the config file.

```json title="annotations.config.json"
{
    "outDirName": "Generated",
    "workspace_common": {
        "shared": {"wally@game-framework": ":Packages"}
    },
    "workspaces": {
        "game": {
            "client": {"src/client": ":"},
            "server": {"src/server": ":"},
            "shared": {"src/shared": ":"}
        }
    },
    "optional_extensions": {
        "unit-test": ["library", "lua_annotations.extensions.unit_tests.main"]
    },
    "tests": {
        "root": "test",
        "outDirName": "Generated"
    },
    "extensions": [
        ["library", "lua_annotations.extensions.game_framework.main"],
        {"kind": "path", "expr": "tools/my_extension.py"}
    ]
}
```

## `outDirName`
The name of the directory where generated files are placed. It is relative to the root of each environment per workspace.

!!! note
    `out_dir` is still accepted for older config files, but `outDirName` is preferred.

Don't forget to add this directory to your `.gitignore`!
```gitignore title=".gitignore"
**Generated/
```

## `workspaces`
`workspaces` is now a dictionary of named workspaces. The object key is the workspace name, which is also used by the unit-test manifest.

Each workspace must contain an environment map with the `client`, `server`, and `shared` keys. Each environment value is a map of filesystem paths, relative to the config directory, to the Lua expression for that path at runtime. The `:` character is replaced with the environment root.

!!! tip
    Each environment can contain multiple processed paths, but the first one is the root where the `Generated` directory is created.

    Other paths are good for shared packages or common code that should be scanned together with the main source root.

```json title="annotations.config.json"
{
    "workspaces": {
        "hub": {
            "client": {"src/hub/client": ":"},
            "server": {"src/hub/server": ":"},
            "shared": {"src/hub/shared": ":"}
        },
        "game": {
            "client": {"src/game/client": ":"},
            "server": {"src/game/server": ":"},
            "shared": {"src/game/shared": ":"}
        }
    }
}
```

## `workspace_common`
`workspace_common` lets you add the same paths to every workspace without repeating them. It uses the same `client`, `server`, and `shared` maps as a workspace, but each key is optional.

Workspace-specific paths are still declared first and are used as the environment roots. If a workspace and `workspace_common` define the same path, the workspace value wins.

```json title="annotations.config.json"
{
    "workspace_common": {
        "shared": {
            "src/common/shared": ":Common",
            "wally@game-framework": ":Packages"
        }
    },
    "workspaces": {
        "game": {
            "client": {"src/client": ":"},
            "server": {"src/server": ":"},
            "shared": {"src/shared": ":"}
        }
    }
}
```

### Path tags
Instead of a literal filesystem path and Lua expression, you may use a tag to resolve paths automatically.

`wally`: resolves a path based on a package name (`my-package`, in this example). The value must be the package directory at Lua runtime, such as `:Packages`.

```json title="annotations.config.json"
{
    "workspaces": {
        "game": {
            "client": {"src/client": ":"},
            "server": {"src/server": ":"},
            "shared": {"src/shared": ":", "wally@my-package": ":Packages"}
        }
    }
}
```

## `extensions`
`extensions` is a list of Python extension modules that are always imported and processed by the CLI tool. Each extension module should contain a `load(ctx)` function which uses the `Extension` API.

Extension entries may be written as a two-item list:

```json
["path", "tools/my_extension.py"]
```

Or as an object:

```json
{"kind": "path", "expr": "tools/my_extension.py"}
```

The `kind` value must be either `library` or `path`.

* `library`: imports the configured Python module from the current environment, such as `lua_annotations.extensions.game_framework.main`.
* `path`: imports a Python file relative to the project directory.

## `optional_extensions`
`optional_extensions` is a named object with the same extension entry format as `extensions`. These extensions are only loaded when selected from the CLI.

```json title="annotations.config.json"
{
    "optional_extensions": {
        "unit-test": ["library", "lua_annotations.extensions.unit_tests.main"],
        "my-tooling": {"kind": "path", "expr": "tools/my_extension.py"}
    }
}
```

## `tests`
`tests` configures the bundled unit-test extension.

* `root`: test source root to scan. Default: `test`
* `outDirName`: generated test manifest directory under `tests.root`. Default: `Generated`

```json title="annotations.config.json"
{
    "tests": {
        "root": "test",
        "outDirName": "Generated"
    }
}
```
