# Local testing
You can require the generated manifest directly in local Luau tests and call its APIs yourself. This is useful when you want to test annotation wiring without relying on the generated `AnnotationInit` bootstrap.

The Luau fixture tests under `test/luau/` use this pattern directly.

## Requiring the manifest
For server code:

```lua title="test/luau/test_manifest_api.lua"
local ServerScriptService = game:GetService("ServerScriptService")
local ServerManifest = require(ServerScriptService.Generated.Manifest)
```

For client code:

```lua title="test/luau/test_manifest_api.lua"
local Players = game:GetService("Players")
local player = Players.LocalPlayer

local ClientManifest = require(player.PlayerScripts.Generated.Manifest)
```

## Calling the core API

The core manifest API contains the following methods:

- `Manifest:getCached(moduleName)`: get a module without running manifest hooks.
- `Manifest:getModule(moduleName)`: alias for `getCached`
- `Manifest:loadModule(moduleName)`: load one module and run annotation handlers and module handlers for it.
- `Manifest:runPreInitHooks()`: run `@onInit` hooks.
- `Manifest:loadAllModules()`: load all manifest modules, respecting load_order when present.
- `Manifest:runPostInitHooks()`: run `@onPostInit` hooks.

Example:

```lua title="test/luau/test_manifest_api.lua"
local SharedService = ServerManifest:getModule("SharedService")
assert(SharedService.initialized == false)

local module = ClientManifest:loadModule("SharedService")
assert(module.initialized == true)
```

If you want the full runtime startup sequence without using `AnnotationInit`, run the same three manifest methods manually:

```lua title="test/luau/test_middleware.lua"
ServerManifest:runPreInitHooks()
ServerManifest:loadAllModules()
ServerManifest:runPostInitHooks()
```

In many tests, `loadAllModules()` is enough by itself because it runs retained annotation handlers and module handlers for every manifest module:

```lua title="test/luau/test_middleware.lua"
ServerManifest:loadAllModules()
ClientManifest:loadAllModules()
```

## Testing game-framework APIs
When the game-framework extension is loaded, the following two methods are injected:

- `Manifest:startService(serviceName, deps?)`: start a service/component/initService, optionally with a custom deps table.
- `Manifest:getServiceDeps(serviceName, runDependencyInit?)`: build the deps table for a service, optionally without running dependency _init.

`startService()` example:

```lua title="test/luau/test_manifest_api.lua"
ServerManifest:startService("ServiceA")

local controller = ClientManifest:startService("ControllerA")
assert(controller.ping() == "pong")
```

And for dependency inspection:

```lua title="test/luau/test_manifest_api.lua"
local deps = ClientManifest:getServiceDeps("ControllerA")
assert(deps.server.ServiceA ~= nil)
```

## Middleware and remote setup
If your test uses remotes, create the expected generated remote instances first.

```lua title="test/luau/test_manifest_api.lua"
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Generated = ReplicatedStorage:FindFirstChild("Generated")
if not Generated then
    Generated = Instance.new("Folder", ReplicatedStorage)
    Generated.Name = "Generated"
end

local Remotes = Generated:FindFirstChild("Remotes")
if not Remotes then
    Remotes = Instance.new("Folder", Generated)
    Remotes.Name = "Remotes"
end
```

After that, you can load the manifests and test the runtime behavior. For example, the middleware fixture verifies that the eleventh request is blocked:

```lua title="test/luau/test_middleware.lua"
ServerManifest:loadAllModules()
ClientManifest:loadAllModules()

local controller = ClientManifest:getModule("ControllerA")
local result = controller.ping()
assert(result.status == "error")
```
