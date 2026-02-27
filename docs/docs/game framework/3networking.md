# Networking
Networking is made easy! It is largely done through the `@remote` annotation. This creates a remote event/function at build-time and injects it into services at runtime.

To define a remote:
```lua title="client/MessageController.lua"
--@service
local controller = {}

--@remote, event
function controller.printMessage(message: string)
	print("Recieved message " .. message)
end

return controller
```

The `@remote` annotation takes one argument, that being a literal `event`, `function`, or `unreliable` string, which corresponds to the underlying Roblox instance to use.


!!! note
    Methods with the `@remote` annotation must be defined with the `.` syntax, not with the self-passing `:` syntax.


On the server side, we can import remote services by prefixing them with `:client`.


```lua title="server/GreetService.lua"
local Players = game:GetService("Players")

--@service, depends=[client:MessageController]
local service = {}

function module:_init(deps)
	self.deps = deps

	task.spawn(function()
        while task.wait(1) do
            for _, player in ipairs(Players:GetPlayers()) do
                self.deps.client.MessageController.printMessage(player, 'Hello, ' .. player.Name)
            end
        end
    end)
end

return service
```