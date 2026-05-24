-- Generated using lua-anot; do not edit manually.
local t0 = os.clock()
local RunService = game and game:GetService("RunService")
local isStudio = RunService and RunService:IsStudio()

local Manifest = require(script.Parent:WaitForChild("Manifest"))

local data = Manifest.manifest


local function getHookFun(hook)
    if not hook then
        return nil
    end

    return Manifest.getCached(hook.module)[hook.method]
end


local function runModuleHandlers(moduleData, moduleName)
    if not moduleData then
        return
    end

    for _, hook in ipairs(data.hooks.module_handlers) do
        local fun = getHookFun(hook)
        if fun then
            fun(Manifest, moduleData, moduleName)
        end
    end
end


--pre_init
local preInitT0 = os.clock()
for _, hook in ipairs(data.hooks.pre_init) do
    local fun = getHookFun(hook)
    if fun then
        fun(Manifest)
    end
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
end

if #data.load_order > 0 then
    for _, moduleName in ipairs(data.load_order) do
        local module = data.modules[moduleName]
        runModuleHandlers(module and module.data, moduleName)
    end
else
    for moduleName, module in pairs(data.modules) do
        runModuleHandlers(module.data, moduleName)
    end
end
local moduleTime = os.clock() - moduleT0


--post_init
local postInitT0 = os.clock()
for _, hook in ipairs(data.hooks.post_init) do
    local fun = getHookFun(hook)
    if fun then
        task.spawn(fun, Manifest)
    end
end
local postInitTime = os.clock() - postInitT0


if isStudio then
    print("[LuaAnnotations] {env} loaded in " .. (os.clock() - t0) .. "s (pre_init=" .. preInitTime .. "s, modules=" .. moduleTime .. "s, post_init=" .. postInitTime .. "s)")
end
