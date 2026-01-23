local ServerScriptService = game:GetService("ServerScriptService")
local T = require(ServerScriptService.generated.Types)

local INIT_DATA: T.PlayerData = {
    money = 0,
    level = 0
}

--@service, depends=[client:DataController]
local service = {
    data = {}
}

function service:_init(deps: T.DataServiceDeps)
    self.DataController = deps.client.DataController
end

function service:set(player: Player, data: PlayerData)
    self.data[player.UserId] = data
end

function service:update(player: Player, data: T.PlayerDataPatch)
    for key, value in pairs(data) do
        self.data[player][key] = value
    end

    self.DataController:updateData(player, data)
end

--@remote, function
function service:get(player: Player): T.PlayerData
    return self.data[player.UserId] or INIT_DATA
end

return service