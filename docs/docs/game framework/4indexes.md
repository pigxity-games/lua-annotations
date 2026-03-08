# Indexes
This is the framework's solution to reducing manual requires for utility modules. As paths change, it may get annoying to constantly update requires for every module that uses it. 

Thus, it is recommended to use the `@indexed` annotation for any modules utility modules, classes, etc. This places modules inside of a "index" module which returns a list of these modules.

!!! warning
    Note that indexes may cause circular dependency issues if misused. They should only be used for pure-data utility modules used frequently in other places of your code.
    
    For accessing indexed modules from another indexed module, just use relative requires.

For example, say we have a simple utility module:
```lua title="MyUtils.lua"
--@indexed
local module = {}

function module.printHello()
    print("Hello World!")
end

return module
```

We can then import it from anywhere else:
```lua
local ReplicatedStorage = game:GetService("ReplicatedStorage")
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

## IndexedType
`@indexedType` follows a similar concept, except with a type scope.
This places any annotated types inside of `Generated/Types/Index.lua`.