local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Utility = require(ReplicatedStorage.Utility)

--@service
local m = {
	initialized = false
}

function m._init(deps)
	m.deps = deps
	m.initialized = true
end

function m.getPingMessage()
	return Utility.pingMessage
end

return m
