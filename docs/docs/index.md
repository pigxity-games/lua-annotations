# Installation
lua-annotations has two installation steps - one for the core python CLI tool (`lua-annotations`), allowing you to create custom annitations, and optionally, `default-framework`, which provides a set of annotations that use the build tool's API to create a Roblox game framework.

!!! note
    This guide assumes that you already have a Rojo project set up. If not, you may follow the tool's [official documentation.](https://rojo.space/docs)

## Build Tool
Install the python tool
```bash
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
## Framework Extension
This provides a Roblox game framework you could optionally use. It is automatically installed with the python package but not automatically imported - add it as an extension to your config.

!!! tip
    You may follow these steps to install any other third-party python extension or even create your own! (more info in the lua-annotations API guide)

```json title="annotations.config.json"
"extensions": [
	["library", "lua-annotations.extensions.game_framework.main"],
]
```
You would also need to install the lua runtime extension. This would need to be installed inside your project directory and added to your `annotations.config.json` and rojo `.project.json` files.
You may either install it using a git submodule or a Wally package.