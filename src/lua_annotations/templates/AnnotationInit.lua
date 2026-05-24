-- Generated using lua-anot; do not edit manually.
local t0 = os.clock()
local RunService = game and game:GetService("RunService")
local isStudio = RunService and RunService:IsStudio()

local Manifest = require(game:GetService("{env-service}")
    :WaitForChild("{out-dir-name}")
    :WaitForChild("Manifest"))

local data = Manifest.manifest


local function getHookFun(hook)
    return Manifest.getCached(hook.module)[hook.method]
end


--pre_init
local preInitT0 = os.clock()
for _, hook in ipairs(data.hooks.pre_init) do
    local fun = getHookFun(hook)
    fun(Manifest)
end
local preInitTime = os.clock() - preInitT0


--modules
local moduleT0 = os.clock()
for moduleName, module in pairs(data.modules) do
    local moduleData = module.data
    
    for methodName, anot in pairs(module.annotations) do
        local anotHook = data.hooks.annotation_handlers[anot.name]
        local fun = getHookFun(anotHook)
       
        if fun then
            fun(Manifest, anot, methodName, moduleData, moduleName)
        end
    end

    local hooks = data.hooks.module_handlers
    for _, hook in ipairs(hooks) do
        local fun = getHookFun(hook)
        fun(Manifest, moduleData, moduleName)
    end
end
local moduleTime = os.clock() - moduleT0


--post_init
local postInitT0 = os.clock()
for _, hook in ipairs(data.hooks.post_init) do
    local fun = getHookFun(hook)
    task.spawn(fun, Manifest)
end
local postInitTime = os.clock() - postInitT0


if isStudio then
    print("[LuaAnnotations] {env} loaded in " .. (os.clock() - t0) .. "s (pre_init=" .. preInitTime .. "s, modules=" .. moduleTime .. "s, post_init=" .. postInitTime .. "s)")
end