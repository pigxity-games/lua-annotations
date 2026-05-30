--@service, depends=[server:ServiceA]
local m = {}

function m._init(deps)
    m.ServiceA = deps.server.ServiceA
end

function m.ping()
    return m.ServiceA.pingRemote()
end

return m
