--@service
local module = {}

--@remote, event
function module.printMessage(message: string)
	print("Recieved message " .. message)
end

--@remote, function
function module.test(param: string): string
	return param * 2
end

return module
