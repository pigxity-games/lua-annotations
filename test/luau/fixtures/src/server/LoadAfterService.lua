--@service, load_after=[ServiceB]
local service = {
    initialized = false
}

function service._init(deps)
    service.initialized = true
    service.deps = deps
end

return service
