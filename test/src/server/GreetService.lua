local Players = game:GetService("Players")
local ServerScriptService = game:GetService("ServerScriptService")
local T = require(ServerScriptService.generated.Types)

--@service, depends=[client:MessageController, DataService]
local module = {}

function module:_init(deps: T.GreetServiceDeps)
	self.MessageController = deps.MessageController
	self.DataService= deps.DataService
end

function module:_start()
	local startTick = tick()

	while task.wait(1) do
		for player in Players:GetPlayers() do
			self.MessageController:printMessage('Hello, ' .. player.Name)
			self.DataService:update(player, {money = tick() - startTick})
		end
	end
end

return module
