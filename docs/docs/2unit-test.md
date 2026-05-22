# Unit Tests
You can create local unit tests for services or modules without running Studio. Unit testing is a separate extension, similar to `game-framework`, and it adds one annotation: `@testCase`.

It is recommended to add the extension to `optional_extensions` so it does not run on every build.

```json title="annotations.config.json"
{
    "optional_extensions": {
        "unit-test": ["library", "lua_annotations.extensions.unit_tests.main"]
    },
    "tests": {
        "root": "test",
        "outDirName": "Generated"
    }
}
```

## `@testCase`
Use `@testCase` on a method to define a lune-test case.

If you also use the `game-framework` extension, the `depends` argument may be used to inject dependencies into the test. This builds a fresh dependency graph for each case and runs `_init` for nested services unless `skip_init=true`.

The annotation supports these keyword arguments:

* `name=str`: custom case name. By default, the function name is used.
* `args={...}`: static args table passed directly to lune-test.
* `depends=[...]`: inject `game-framework` services into the test.
* `skip_init=bool`: only valid with `depends`. If `true`, `_init()` is not run.
* `workspaces=[hub, game]`: override the workspace selection for that case.

`args` and `depends` are mutually exclusive.

## Single-workspace example
Say you have the following service:

```lua title="src/server/TestService.lua"
--@service, depends=[DataService]
local m = {}

function m._init(deps)
    m.DataService = deps.DataService
end

function m.add(a: number, b: number)
    return a + b
end

function m.getDataValue(userId: number)
    return m.DataService.data[userId]
end

return m
```

You can then create tests for it:

```lua title="test/test_service_tests.lua"
--@module
local m = {}

--@testCase, depends=[TestService]
function m.addFunctionAddsTwoNumbers(deps)
    local add = deps.TestService.add

    assert(add(1, 1) == 2, '1+1 is not 2')
    assert(add(2, 2) == 4, '2+2 is not 4')
end

--@testCase, depends=[TestService], skip_init=true
function m.getDataValueReturnsPlayerData(deps)
    local service = deps.TestService

    service.DataService = {
        data = {
            [123] = {level = 5}
        }
    }

    assert(service.getDataValue(123).level == 5, 'Level for player 123 is not 5')
end

--@testCase, args={12, 3, 4}
function m.staticArgsExample(a, b, c)
    assert(a == 12 and b == 3 and c == 4, 'Args were not passed correctly')
end

return m
```

!!! tip
    `lune-test` runs each case in a sandboxed environment. Modifying service data in one test does not affect any other case.

The `game-framework` extension is optional, but `depends` requires it. To create a test for a utility or pure-data module, simply require it using a string path:

```lua
local Module = require('../src/shared/SomeModule.lua')
```

Since `lune-test` emulates a Roblox environment, Roblox instance-based requires should work for nested modules.

## Workspace selection
The unit-test manifest is workspace-aware.

### Folder convention
If the first path segment under `tests.root` matches a workspace name, the test file defaults to that workspace.

```text
test/
    hub/
        inventory_tests.lua
    game/
        combat_tests.lua
```

In this example, `test/hub/inventory_tests.lua` runs in the `hub` workspace and `test/game/combat_tests.lua` runs in the `game` workspace.

### Shared tests for multiple workspaces
For shared test modules, use `workspaces=[...]` on each `@testCase`.

```lua title="test/common_tests.lua"
--@module
local m = {}

--@testCase, workspaces=[hub, game]
function m.commonContract()
end

return m
```

This produces one suite per selected workspace. Root-level test files without `workspaces=[...]` are only allowed when the project has exactly one workspace.

## Building the manifest
After writing your tests, build the manifest:

```sh
lua-anot build -e unit-test
```

When the extension is listed under `optional_extensions`, normal `lua-anot build` does not output the test manifest automatically.

To build both your project and all optional extensions, use:

```sh
lua-anot build -e all
```

You may repeat `-e` to enable multiple optional extensions:

```sh
lua-anot build -e unit-test -e other-extension
```

By default, the manifest is written to `test/Generated/Manifest.lua`.

## Manifest shape
The bundled extension emits one workspace-aware lune-test manifest:

```lua
return {
    workspaces = {
        hub = {
            mounts = {
                ReplicatedStorage = {
                    _root = './src/hub/shared',
                    Common = './src/common/shared',
                },
                ServerScriptService = {
                    _root = './src/hub/server',
                    Common = './src/common/server',
                },
                PlayerScripts = {
                    _root = './src/hub/client',
                    Common = './src/common/client',
                },
            },
        },
    },

    tests = {
        hub_tests = {
            workspace = 'hub',
            module = './hub_tests',
            cases = {
                someTestCase = function()
                    return createDependencies('hub', {'Service1', 'Service2'}, false)
                end,
            },
        },

        game_common_tests = {
            workspace = 'game',
            module = './common_tests',
            cases = {
                someGameTestCase = {},
            },
        },
    },
}
```

Mounts are derived from each workspace and `workspace_common`.

* `shared` mounts to `ReplicatedStorage`
* `server` mounts to `ServerScriptService`
* `client` mounts to `PlayerScripts`

Runtime expressions are translated like this:

* `:` becomes `_root`
* `:Common` becomes `Common`
* nested expressions such as `:Packages.Framework` become nested mount tables

## Installing `lune-test`
This manifest is designed to work with [lune-test](https://github.com/pigxity-games/lune-test).

First, install `lune` via rokit:

```sh
rokit add lune
```

Then download the lune-test script and place it under `~/.lune/`.

## Running tests
Run `lune-test` pointing to the manifest file to run all tests:

```sh
lune run lune-test test/Generated/Manifest.lua
```

Or to only run a specific suite:

```sh
lune run lune-test test/Generated/Manifest.lua test_service_tests
```
