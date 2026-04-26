# Services
Services are single-instanced modules (singletons) that represent game features that you really only need one of.

!!! question "Controllers?"
    Unlike other frameworks, there is no concept of "client controllers." Instead, services can be placed on both the server and client.
    
    Nevertheless, it would still be a good idea to enforce a convention to name clientside services as "Controllers" for clarity.


## Creating a simple service
First, let's define a simple service.

```lua title="src/server/GreetService.lua"
--@service
local service = {}

function service._init()
    print('Hello World!')
end

function service.greet(name: string)
    print('Hello ' .. name .. '!')
end

return service
```

!!! warning
    Do not place blocking or heavy code inside of a service's `_init()` method as it yields before the next service can start. Instead, you should use the Roblox `task.spawn` or `task.defer` functions. Also note that this method along with any annotated methods should be defined with `.` instead of `:`.

## Dependency injection
This project aims to reduce the need for manual requires as much as possible. Thus, the preferred way to utilize services is through dependency injection (DI).
It is a technique where an object receives dependencies externally rather than internally.

In this case, the runtime loader injects other services into the constructors of services that require them.
Utilizing this would decouple your game features and thus allow for modular code, easier testing, and easier refactors.

Let's create a new service that utilizes the `greet()` method of the above `GreetService`.

```lua title="src/server/PlayerService.lua"
local Players = game:GetService('Players')

--@service, depends=[GreetService]
local service = {}

function service._init(deps)
    service.deps = deps

    Players.PlayerAdded:Connect(function(player)
        deps.GreetService.greet(player.Name)
    end)
end


return service
```

In this example:

- The `depends` argument accepts a list of service names to inject.
- The `deps` parameter is a table which contains the injected services at runtime.
- We store the `deps` object inside the module so that we can access it in other functions.
- `Generated/ServiceTypes.lua` contains generated service and dependency types.

!!! note
    The build tool automatically determines the load order of services based on `depends` and `load_after`.

## `load_after`
`load_after` affects load order without injecting the target into `deps`. This is useful when one service needs another service to exist first, but should not call it directly.

```lua
--@service, load_after=[DataService]
local service = {}

return service
```

## `@initService` 
This annotation basically allows you to use a function as a service. It's great for any one-time loaders which require dependencies.

It's effectively the same as defining a service with only an `_init()` method.

```lua
local Players = game:GetService('Players')
local m = {}

--@initService, depends=[GreetService]
function m.greetPlayer(deps)
    Players.PlayerAdded:Connect(function(player)
        deps.GreetService.greet(player.Name)
    end)
end

return m
```

## `@dependency`
This is a simple annotation which `@service`, `@initService`, and `@component` inherit from. Modules annotated with it **are not loaded automatically at runtime**, ie they have no `_init` method. Use this for pure data modules which still need DI or generated types.

```lua title="src/server/BalanceConfig.lua"
--@dependency
local config = {
    startingCoins = 100,
}

return config
```

You may also use `typegen=registry` for component registries. More info is in the component docs.
