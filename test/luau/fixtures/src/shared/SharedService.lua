--@service
local m = {
    initialized = false
}

function m._init()
    m.initialized = true
end

function m.add(a, b)
    return a + b
end

return m
