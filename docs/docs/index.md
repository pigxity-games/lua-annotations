# Installation
lua-annotations has two parts: the core python CLI tool (`lua-annotations`), allowing you to create custom annotations, and the optional game framework extension, which provides a set of Roblox-focused annotations built on top of the core API.

!!! note
    This guide assumes that you already have a Rojo project set up and you are familiar with the tool. If not, you may follow the tool's [official documentation.](https://rojo.space/docs)

## Installing with pip
### Build Tool
Install the python tool:
```sh
pip install lua-annotations
```
Create a config file for your project:
```json title="annotations.config.json"
{
    "outDirName": "Generated",
    "workspaces": [
        {
            "client": {"src/client": ":"},
            "server": {"src/server": ":"},
            "shared": {"src/shared": ":"}
        }
    ]
}
```
If you wish to add a Wally package to be processed, you may add it like this:
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

### Framework Extension
This provides a Roblox game framework you can optionally use. It is installed with the python package but not automatically imported - add it as an extension to your config.

!!! tip
    You may follow these steps to add path-based third-party extensions or create your own! More info is in the lua-annotations API guide.

```json title="annotations.config.json"
{
    "extensions": [
        ["library", "lua_annotations.extensions.game_framework.main"]
    ]
}
```
Lua runtime code is added to your project automatically under `Generated/_Internal`.

## Installing from source
Clone the git repository:
```sh
git clone https://github.com/pigxity-games/lua-annotations
```

Install via pip:
```sh
pip install -e ./lua-annotations
```
