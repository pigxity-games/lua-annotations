--@service, depends=[ServiceB]
local m = {}

function m._init(deps)
	m.ServiceB = deps.ServiceB
end

function m.ping()
	return m.ServiceB.getPingMessage()
end

--@remote, function
function m.pingRemote()
	return m.ping()
end

return m
