# Components
Unlike services, components represent **individual Roblox instances** which are bound by CollectionService tags. They usually control services.

## Simple components (@bindTag)
For simplicity, we'll start with the `@bindTag` annotation, which could be considered as a "simple component" of some sorts. It bind to a function which is called for each tagged instance. This is good for simple objects that you have a lot of, such as obby killbricks.

```lua name="src/server/KillBrick.lua"
--@module
local module = {}

--@bindTag, [KillBrick]
function module.killBrick(inst: BasePart)
    local conn = inst.Touched:Connect(function(p)
        local hum = p.Parent:FindFirstChild("Humanoid") :: Humanoid
        if hum then
            hum.Health = 0
        end
    end)
    return function()
        conn:Disconnect()
    end
end

return module
```

In this example: 

- The `@module` annotation simply indexes the module to be processed by the parser.
- We bind a `Touched` listener to the instance, which kills any model with a `Humanoid`.
- We return a cleanup function that disconnects  the listener, running on tag remove.

