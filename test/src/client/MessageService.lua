--@service
local module = {}

--@connect #RemoteEvent, ClientSendMessage
function module.printMessage(message: string)
	print("Recieved message " .. message)
end

return module
