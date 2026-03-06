# Components
Unlike services, components represent **individual Roblox instances** which are bound by CollectionService tags. They usually control services.

## Simple components (`@bindTag`)
For simplicity, we'll start with the `@bindTag` annotation, which could be considered as a "simple component" of some sorts. It bind to a function which is called for each tagged instance. This is good for simple objects that you have a lot of, such as obby killbricks.


```lua title="src/server/KillBrick.lua"
--@module
local module = {}

--@bindTag, KillBrick
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
--@component, Counter
local counter = {
    count = 0
}

function counter:_init(inst: BasePart)
    self.instance = inst
    local detector: ClickDetector = inst:WaitForChild("ClickDetector")
    local label: TextLabel = inst.SurfaceGui.TextLabel

    self.conn = detector.MouseClick:Connect(function(player)
        self:increment(player)
    end)
end

function counter:increment(player: Player)
    self.count += 1
    label.Text = "Count: " .. self.count
end

function counter:_destroy()
    self.conn:Disconnect()
end
```

!!! note
    At runtime, this module will be converted to a multi-instanced class. Components defined like this require an `_init()` method, for injecting the instance and services, and a `_destroy()` method, which is called on component remove.

    To inject a service, simply do so like another service. Note that you cannot inject components into services, due to their multi-instanced nature. If you would like to create components programatically, you should add a tag to the instance. 

## Depending on components

Sometimes you may want to add additional, optional functionality to a component based on another component. To do this, we may depend on the other component from the main component.

Consider our counter example. Let's say we want to add a "logger" component which periodically prints the counter's `count` value. We could put this inside of the same file as the counter for simplicity.

```lua
--@component, CounterLogger, depends=[Counter]
local logger = {
    active = True
}

function logger:_init(inst: BasePart)
    self.inst = inst
    self.Counter = deps.Counter

    task.spawn(function()
        while active do
            print("Counter: " .. self.inst.Name .. " : count = " .. self.Counter.count)
            task.wait(3)
        end
    end)
end

function logger:_destroy()
    self.active = False
end


return {
    Counter = counter,
    CounterLogger = logger
}
```

!!! note
    * We create an `active` field inside of the component as loops do not automatically end upon component removal.
    * Returning a table like this exports the components as "submodules," allowing you to return multiple per file (more info in the `core` docs).

## The `data` argument
You may use the `data` kwarg to specify a path to a "component registry". When a comonent is created, it uses data from this table to create it. This allows for specifying initial data or for easy access of components from elsewhere.

Registries are simple tables that map instances to initial data. If some instances here do not have the component tag, it is automatically added.

```lua title="src/client/registries/CounterRegistry.lua"
--@dependency, load_after=[Counter]
local m = {
    [workspace.Part1] = {
        val = 123
    },
    [workspace.Part2] = {}
}

return m
```

!!! note
    * A dependency is similar to a service, except that it is not loaded at runtime. It's useful for modules which contain pure data that you still want/need to DI.
    * Each registry may only be used for one component class.

Creating the component:

```lua title="src/client/Counter.lua"
--@component, Counter, data=CounterRegistry
local counter = {
    val = 0
}

function counter:_init(inst: BasePart, deps)
    print(self.val)
    --Counter logic...
end

return counter
```

You may then access the counter registry via dependency injection.

```lua
function service:_init(deps)
    local Counters = deps.CounterRegistry

    --getting a component
    local counter1 = Counters[workspace.Part1]
    counter1:increment()
    print(counter1.val)

    --creating a new component (`.create()` is added at runtime)
    local counter3 = Counters.c`reate(workspace.Part3, {val = 123})
end
```