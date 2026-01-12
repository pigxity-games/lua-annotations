local ReplicatedStorage = game:GetService("ReplicatedStorage")

--@dependency
local module = {}

function module.sendClientMessage(player: Player, message: string)
	ReplicatedStorage.generated.ClientSendMessage:FireClient(player, message)
end

return module
