-- Generated using lua-anot; do not edit manually.
local m = {}

--{paths}

--{manifest}

local cache = {}

local function waitForPath(path)
    local cur = path[1]
    for i = 2, #path do
        cur = cur:WaitForChild(path[i])
    end
    return cur
end

function m.getCached(moduleName)
    local m = cache[moduleName]
    if not m then
        m = require(waitForPath(m.paths[moduleName]))
        cache[moduleName] = m
    end
    return m
end

--{method_appends}
    
return m