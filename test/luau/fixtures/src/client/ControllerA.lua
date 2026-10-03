-- Exercises client service dependency injection so remote proxy contracts can be validated.

local ServiceTypes = require(script.Parent.Generated.ServiceTypes)

--@service, depends=[server:ServiceA]
local m = {}

function m._init(deps: ServiceTypes.ControllerADeps)
	m.ServiceA = deps.server.ServiceA
end

function m.ping(): string
	return m.ServiceA.pingRemote()
end

return m
