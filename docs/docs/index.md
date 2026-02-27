# Installation
lua-annotations has two installation steps - one for the core python CLI tool (`lua-annotations`), allowing you to create custom annitations, and optionally, `default-framework`, which provides a set of annotations that use the build tool's API to create a Roblox game framework.

!!! note
    This guide assumes that you already have a Rojo project set up and you are familiar with the tool. If not, you may follow the tool's [official documentation.](https://rojo.space/docs)

## Using a package manager
### Build Tool
Install the python tool
```sh
pip install lua-annotations
```
Create a config file for your project.
```json title="annotations.config.json"
{
	"outDirName": "Generated",
    "workspaces": [
        {
            "client": {"src/client": ":"},
            "server": {"src/server": ":"},
            "shared": {"src/shared": ":"}
        }
    ],
}
```
If you wish to add a Wally package to be processed, you may add it like this:
```json title="annotations.config.json"
"workspaces": [
	"shared": {..., "wally@my-package": ":Packages"}
]
```

----
### Framework Extension
This provides a Roblox game framework you could optionally use. It is automatically installed with the python package but not automatically imported - add it as an extension to your config.

!!! tip
    You may follow these steps to install any other third-party python extension or even create your own! (more info in the lua-annotations API guide)

```json title="annotations.config.json"
"extensions": [
	{
        "kind": "library", 
        "expr": "lua-annotations.extensions.game_framework.main"
    }
]
```
You would also need to install the lua runtime extension. This would need to be installed inside your project directory and added to your `annotations.config.json` and rojo `.project.json` files.
You may either install it using a git submodule or a Wally package.

## From source
Clone the git repository:
```sh
git clone https://github.com/pigxity-games/lua-annotations
```

Install via pip:
```sh
pip install -e ./lua-annotations
```

### Framework Extension
Symlink the `lua/game_framework` directory in the repo to your project

=== "bash"
    ```sh
    ln -s ./lua/game_framework /your/project/game_framework
    ```

=== "powershell (requires admin/devmode)"
    ```ps1
    New-Item -ItemType SymbolicLink -Path ".\lua\game_framework" -Target "\your\project\game_framework" 
    ```

Add the directory to your `annotations.config.json` and your rojo `.project.json`