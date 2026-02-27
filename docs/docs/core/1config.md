# Config format
This is a rundown of the initial config file.

```json title="annotations.config.json"
{
    "out_dir": "Generated",
    "workspaces": [
        {
            "client": {"src/client": ":"},
            "server": {"src/server": ":"},
            "shared": {"src/shared": ":"}
        }
    ],
    "extensions": [
        {
            "kind": "package",
            "value": "my_extension.main",
        },
    ],
    "flags": {
        ...
    }
}
```
## `out_dir`
The name of the directory of where generated files would be placed. Relative to the root of each environment per workspace

Don't forget to add this directory to your `.gitignore`!
```gitignore title=".gitignore"
**Generated/
```

## `workspaces`
These represent individual lua projects which are processed in parallel. Multiple workspaces are especially useful for multi-place Roblox games.

Each workspace must contain an environment map, that is a dictionary with the `client`, `server`, and `shared` keys. Each environment value should contain a map of filesystem paths (relative to the config directory) to lua expressions that represent the path at runtime (where `:` is replaced with the environement root.)

!!! tip
    Each environment can contain multiple processed paths, but the first one is the root. (where the `Generated` directory is created)
    
    Other paths are good for having packages be processed, for example.

### Path tags
Instead of a literal filesystem path and lua expression, you may use a tag to resolve paths automatically.

`wally`: resolves a path based on a package name (`my-package`, in this example). The value must be the package directory at lua runtime (such as `:Packages`)
```json title="annotations.config.json"
"workspaces": [
	"shared": {..., "wally@my-package": ":Packages"}
]
```

## `extensions`
A list of python package names to be imported and processed by the CLI tool. These should contain a `load()` function at the root module which utilizes the `Extension` API. `kind` must either be `package` or `path`, where `value` should be the package name or filepath, respectively.

## `flags`
A list of boolean flags which can modify behavior of the tool or of extensions:

**game_framework:**

* `game_framework.service_typegen`: whether to generate type files for services (True)