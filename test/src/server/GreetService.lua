local ServerScriptService = game:GetService("ServerScriptService")
local T = require(ServerScriptService.generated.Types)
local Network: T.Network

--@service
local module = {}

--@inject Network
function module._init(deps: T.GreetServiceDeps)
	Network = deps.Network
end

--@connect game:Players.PlayerAdded
function module.sendGreeting(player: Player)
	Network.sendClientMessage(player, "Hello, " .. player.Name)
end

return module
