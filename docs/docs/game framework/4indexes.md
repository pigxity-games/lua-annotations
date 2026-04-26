# Indexes
This is the framework's solution to reducing manual requires for utility modules. As paths change, it may get annoying to constantly update requires for every module that uses it. 

Thus, it is recommended to use the `@indexed` annotation for utility modules, classes, and other pure modules you need often. This places modules inside of an `Index` module which returns a table of these modules.

!!! warning
    Note that indexes may cause circular dependency issues if misused. They should only be used for pure-data utility modules used frequently in other places of your code.
    
    For accessing indexed modules from another indexed module, just use relative requires.

For example, say we have a simple utility module:
```lua title="MyUtils.lua"
--@indexed
local module = {}

function module.printHello()
    print('Hello World!')
end

return module
```

We can then import it from anywhere else:
```lua
local ReplicatedStorage = game:GetService('ReplicatedStorage')
local Index = require(ReplicatedStorage.Generated.Index)
local MyUtils = Index.MyUtils

MyUtils.printHello()
```

The annotation also accepts an argument, which places the indexed module in a nested table which is inside of the index.

For example, you define an indexed module with `@indexed, Utils`. You can then import it as follows:
```lua
local MyUtils = Index.Utils.MyUtils
MyUtils.printHello()
```

## Naming indexed modules
By default, the key is the module's returned name. You may override it with the `name` kwarg:

```lua title="MathUtil.lua"
--@indexed, Utils, name=Math
local module = {}

return module
```

This may be imported as:

```lua
local Math = Index.Utils.Math
```

## Generated service types
The index extension also writes `Generated/ServiceTypes.lua`. This file contains generated types for services, components, dependencies, dependency injection tables, and remote dependency wrappers.

There is no separate `@indexedType` annotation. Type generation is tied to the game framework annotations, such as `@service`, `@component`, and `@dependency`.
