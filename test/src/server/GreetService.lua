local ServerScriptService = game:GetService("ServerScriptService")
local T = require(ServerScriptService.generated.Types)

local MessageService

--@service
--@depends, client:MessageService
local module = {}

function module._init(deps: T.GreetServiceDeps)
	MessageService = deps.MessageService
end

--@connect, game:Players.PlayerAdded
function module.sendGreeting(player: Player)
	MessageService.printMessage('Hello, ' .. player.Name)
end

return module
