# Config format
This is a rundown of the initial config file.

```json title="annotations.config.json"
{
    "outDirName": "Generated",
    "workspace_common": {
        "shared": {"wally@game-framework": ":Packages"}
    },
    "workspaces": [
        {
            "client": {"src/client": ":"},
            "server": {"src/server": ":"},
            "shared": {"src/shared": ":"}
        }
    ],
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
These represent individual lua projects which are processed in parallel. Multiple workspaces are especially useful for multi-place Roblox games.

Each workspace must contain an environment map, that is a dictionary with the `client`, `server`, and `shared` keys. Each environment value should contain a map of filesystem paths (relative to the config directory) to lua expressions that represent the path at runtime. The `:` character is replaced with the environment root.

!!! tip
    Each environment can contain multiple processed paths, but the first one is the root, where the `Generated` directory is created.
    
    Other paths are good for having packages be processed, for example.

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
    "workspaces": [
        {
            "client": {"src/client": ":"},
            "server": {"src/server": ":"},
            "shared": {"src/shared": ":"}
        }
    ]
}
```

### Path tags
Instead of a literal filesystem path and lua expression, you may use a tag to resolve paths automatically.

`wally`: resolves a path based on a package name (`my-package`, in this example). The value must be the package directory at lua runtime (such as `:Packages`)
```json title="annotations.config.json"
{
    "workspaces": [
        {
            "client": {"src/client": ":"},
            "server": {"src/server": ":"},
            "shared": {"src/shared": ":", "wally@my-package": ":Packages"}
        }
    ]
}
```

## `extensions`
A list of python extension modules to be imported and processed by the CLI tool. Each extension module should contain a `load(ctx)` function which utilizes the `Extension` API.

Extension entries may be written as a two-item list:

```json
["path", "tools/my_extension.py"]
```

Or as an object:

```json
{"kind": "path", "expr": "tools/my_extension.py"}
```

The `kind` value must be either `library` or `path`.

* `library`: loads the bundled game framework extension. The usual value is `lua_annotations.extensions.game_framework.main`.
* `path`: imports a python file relative to the project directory.
