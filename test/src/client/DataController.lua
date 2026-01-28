local PlayerScripts = script:FindFirstAncestorOfClass("PlayerScripts")
local T = require(PlayerScripts.generated.Types)

--@controller, depends=[server:DataService]
local controller = {}

function controller:_init(deps: T.DataControllerDeps)
    self.DataService = deps.server. DataService
end

function controller:_start()
    self.data = self.DataService:get()
end

--@remote, event
function controller:updateData(data: T.PlayerDataPatch)
    for key, value in pairs(data) do
        self.data[key] = value
    end
    print(self.data)
end

return controller