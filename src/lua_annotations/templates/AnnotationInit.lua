-- Generated using lua-anot; do not edit manually.

local t0 = os.clock()

--modulePaths

local cache = {}
local function waitForPath(path)
    local cur = path[1]
    for i = 2, #path do
        cur = cur:WaitForChild(path[i])
    end
    return cur
end

local function getCached(moduleName)
    local m = cache[moduleName]
    if not m then
        m = require(waitForPath(modulePaths[moduleName]))
        cache[moduleName] = m
    end
    return m
end


--manifest

--lifecycle
for _, fun in ipairs(manifest.hooks.init) do
    fun(manifest)
end

for _, anot in ipairs(manifest.annotations) do
    local fun = manifest.hooks.annotation_handlers[anot.name]
    if fun then
        fun(anot, manifest)
    end
end

for _, fun in ipairs(manifest.hooks.post_init) do
    task.spawn(fun, manifest)
end

print("[LuaAnnotations] (env) annotations loaded in " .. (os.clock() - t0) .. "s")
