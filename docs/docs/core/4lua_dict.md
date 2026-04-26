# Lua Table Generation
`lua_annotations.api.lua_dict` contains helpers for converting python data into lua tables. The manifest extension uses these helpers to serialize the manifest and `modulePaths`.

```python
from pathlib import PurePath

from lua_annotations.api.lua_dict import LuaExpr, LuaPath, convert_dict_module


def on_post_process(self, ctx):
    data = {
        'message': 'Hello',
        'workspace': LuaExpr('workspace'),
        'util': LuaPath(PurePath('shared/Util.lua'), require=True),
    }

    ctx.create_file('shared', 'MyData.lua', convert_dict_module(ctx, data))
```

Useful classes:

* `LuaExpr`: writes a raw lua expression instead of a quoted string.
* `LuaPath`: converts a filesystem path or environment-prefixed path into a lua expression.
* `LuaPathResolver`: resolves paths against a workspace and tracks required Roblox service imports.
* `convert_dict`: converts python data into a lua table.
* `convert_dict_module`: creates a full lua module with the generated-file header.
* `convert_dict_type`: creates a lua type definition from python data.

## `LuaPath`
`LuaPath` is the most common helper for generated runtime data because it lets generated lua require project modules without hardcoding Roblox paths.

```python
LuaPath(PurePath('shared/Util.lua'), require=True)
```

Important options:

* `require=True`: wraps the resolved path in `require(...)`.
* `properties=['run']`: accesses properties after requiring or resolving the path.
* `function=True`: wraps the expression in `function() return ... end`.
* `cache=True`: uses generated `getCached("ModuleName")` lookup instead of directly requiring the module.
* `relative=True`: creates a `script.Parent...` path for generated files that use relative requires.

!!! tip
    Runtime manifest paths usually use `require=True`, `function=True`, and `cache=True`. That is why manifest values like `getAdornee` are functions instead of required values; the module is only required when the runtime hook needs it.
