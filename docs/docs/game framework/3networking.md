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

    Remote methods must be in client or server code. Shared `@remote` annotations are invalid because networking always goes between the client and server.


On the server side, we can import remote services by prefixing them with the opposite environment name, i.e. `client:` in this example.


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

Cross-environment dependencies must use `client:` or `server:`. The build fails if the named remote service does not exist in that environment.

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

### Generated remotes
The networking extension writes `Generated/Remotes.model.json` in the shared environment. This creates a folder per remote service and a Roblox remote instance per `@remote` method.

## Middleware
You may define functions to be run before a request is sent, received, or before a response is sent for remote functions. These types of functions are called middleware, and can be declared using the `@middleware` annotation.

The annotation has the following syntax:
```
@middleware, {environment: server|client}, {direction: inbound|outbound}, global=boolean, name=string
```

* Environment: on what network side the function should run. If `server`, then `ctx.player` is the sending/receiving player.
* Direction: `inbound` filters by requests entering `environment`, while `outbound` filters by requests leaving `environment`.
* Global: whether the middleware should be applied by default to all remotes. If false or omitted, then remotes have to opt in to the middleware on a case-by-case basis.
* Name: sets a custom name for the middleware. This overrides the function name, which is the default.

Middleware names are used to dedupe a chain per direction. Reusing names can replace named lookup and can make global order confusing, so keep names unique.

!!! warning
    For a request to be successful, all middleware must return `true` as the first value. Otherwise, the request is cancelled for events, or the response of the failing middleware is sent for functions. Any values returned after `true` are passed to the next middleware and eventually to the remote, so you must also pass the arguments across the chain, usually with `...`.

!!! tip
    It may be a good idea to enforce a convention in your project, such as having the first argument of all network requests be a table with `status` and `message`, to fully benefit from middleware.
    ```lua
    {status = 'error', message = 'You are not authorized!'}
    ```

    For example, you may have global client logger middleware which outputs network errors in the chat, and server middleware which sends errors for bad requests.

### Context
Context is always the first argument passed into middleware. It is a table which contains the following:

* `player`: for server middleware only; the player instance sending/receiving the request. For server outbound requests, this may also be a list of players or a literal `'all'`.
* `direction`: the direction of the middleware (same as the arg).
* `service`: the service that sends or receives the request.
* `method`: the method that sends or receives the request.
* `remoteType`: the type of remote (`event|function|unreliable`).

### Examples
Example (logger):
```lua
--@middleware, server, inbound
local function Logger(ctx, ...)
    print(`Request from player: {ctx.player.Name}`)
    print(`Service: {ctx.service} | Method: {ctx.method}`)
    return true, ...
end 

return Logger
```

Example (authentication):
```lua
local ADMINS = {123, 456, 789}

--@middleware, server, inbound
local function RequireAdmin(ctx, ...)
    for _, id in ipairs(ADMINS) do
        if id == ctx.player.UserId then
            return true, ...
        end
    end
    --response sent to client if they are not an admin
    return false, {status = 'error', message = 'You are not authorized!'}
end

return RequireAdmin
```

### Remote Opt-In
To add non-global middleware to specific remotes, you may use the `middleware=[...]` kwarg:
```lua
--@remote, event, middleware=[RequireAdmin]
function service.runAdminCommand(player: Player, command: string)
    print('Ran command: ' .. command)
end
```
