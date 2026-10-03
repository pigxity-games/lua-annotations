-- Exercises server dependency and remote dispatch so generated service contracts can be validated.

local ServiceTypes = require(script.Parent.Generated.ServiceTypes)

--@service, depends=[ServiceB]
local m = {}

function m._init(deps: ServiceTypes.ServiceADeps)
	m.ServiceB = deps.ServiceB
end

function m.ping(): string
	return m.ServiceB.getPingMessage()
end

--@remote, function
function m.pingRemote(): string
	return m.ping()
end

return m
