--@service
local module = {}

--@remote, event
function module.printMessage(message: string)
	print("Recieved message " .. message)
end

return module
