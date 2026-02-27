# Components
Unlike services, components represent **individual Roblox instances** which are bound by CollectionService tags. They usually control services.

## Simple components (@bindTag)
For simplicity, we'll start with the `@bindTag` annotation, which could be considered as a "simple component" of some sorts. It bind to a function which is called for each tagged instance. This is good for simple objects that you have a lot of, such as obby killbricks.


```lua title="src/server/KillBrick.lua"
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


## `@component`
You may want to inject services, store state into components, or pass them in functions like objects. To do so, you need to create a component class.

For example:
```lua title="src/client/Counter.lua"
--@component, [Counter]
local component = {
    count = 0
}

function component:_init(inst: BasePart)
    self.instance = inst
    local detector: ClickDetector = inst:WaitForChild("ClickDetector")
    local label: TextLabel = inst.SurfaceGui.TextLabel

    self.conn = detector.MouseClick:Connect(function(player)
        self.count += 1
        label.Text = "Count: " .. self.count
    end)
end

function component:_destroy()
    self.conn:Disconnect()
end


return component
```

!!! note
    At runtime, this module will be converted to a multi-instanced class. Components defined like this require an `_init()` method, for injecting the instance and services, and a `_destroy()` method, which is called on component remove.

    To inject a service, simply do so like another service. Note that you cannot inject components into services, due to their multi-instanced nature.