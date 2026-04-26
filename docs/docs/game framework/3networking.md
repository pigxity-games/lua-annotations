# Networking
Networking is made easy! It is largely done through the `@remote` annotation. This creates a remote event/function at build-time and injects it into services at runtime.

To define a remote:
```lua title="src/client/MessageController.lua"
--@service
local controller = {}

--@remote, event
function controller.printMessage(message: string)
    print('Received message ' .. message)
end

return controller
```

The `@remote` annotation takes one argument, that being an `event`, `function`, or `unreliable` string, which corresponds to the underlying Roblox instance to use. Use `event` and `function` for normal runtime callbacks; `unreliable` currently only affects the generated remote instance type.


!!! note
    Methods with the `@remote` annotation must be defined with the `.` syntax, not with the self-passing `:` syntax.


On the server side, we can import remote services by prefixing them with the opposite environment name, ie `client:` in this example.


```lua title="src/server/GreetService.lua"
local Players = game:GetService('Players')

--@service, depends=[client:MessageController]
local service = {}

function service._init(deps)
    service.deps = deps

    task.spawn(function()
        while task.wait(1) do
            for _, player in ipairs(Players:GetPlayers()) do
                service.deps.client.MessageController.printMessage(player, 'Hello, ' .. player.Name)
            end
        end
    end)
end

return service
```

Remote dependencies are injected under `deps.client` on the server and `deps.server` on the client. Only methods annotated with `@remote` are included in the generated remote type.

## Remote functions
Use `function` when you need a return value.

```lua title="src/server/DataService.lua"
--@service
local service = {}

--@remote, function
function service.getCoins(player: Player): number
    return 10
end

return service
```

```lua title="src/client/DataController.lua"
--@service, depends=[server:DataService]
local controller = {}

function controller._init(deps)
    local coins = deps.server.DataService.getCoins()
    print(coins)
end

return controller
```

## Remote events
Remote events are fire-and-forget.

When the server calls a client remote event, pass the target player first. You may also pass `'all'` to fire every client, or a list of players to fire several clients.

```lua
deps.client.MessageController.printMessage(player, 'Hello')
deps.client.MessageController.printMessage('all', 'Server restarting')
deps.client.MessageController.printMessage(players, 'Match found')
```

When the client calls a server remote event, call the method with only your payload arguments.

## Generated remotes
The networking extension writes `Generated/Remotes.model.json` in the shared environment. This creates a folder per remote service and a Roblox remote instance per `@remote` method.
