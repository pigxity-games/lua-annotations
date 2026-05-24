-- Generated using lua-anot; do not edit manually.
local m = {}

--{paths}

--{manifest}

local cache = {}
local annotationHandlerMocks = {}

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

local function getAnnotationHandler(name)
    local mock = annotationHandlerMocks[name]
    if mock then
        return mock
    end

    local hook = m.manifest.hooks.annotation_handlers[name]
    if not hook then
        return nil
    end

    return m.getCached(hook.module)[hook.method]
end

function m.getModuleData(moduleName)
    local module = m.manifest.modules[moduleName]
    return module and module.data
end

function m.getAnnotationData(moduleName, methodName)
    local module = m.manifest.modules[moduleName]
    local annotations = module and module.annotations
    return annotations and annotations[methodName]
end

function m.getAnnotationAdornee(moduleName, methodName)
    local module = m.getCached(moduleName)
    if methodName == "_module" then
        return module
    end

    return module[methodName]
end

function m.setAnnotationHandler(name, handler)
    annotationHandlerMocks[name] = handler
end

function m.clearAnnotationHandler(name)
    annotationHandlerMocks[name] = nil
end

function m.runModuleAnnotations(moduleName, options)
    local module = assert(m.manifest.modules[moduleName], ("[LuaAnnotations] Unknown module %q"):format(moduleName))

    for methodName, anot in pairs(module.annotations) do
        local handler = getAnnotationHandler(anot.name)
        if handler then
            handler(m, anot, methodName, module.data, moduleName, options)
        end
    end
end

function m.runAllAnnotations(options)
    for moduleName in pairs(m.manifest.modules) do
        m.runModuleAnnotations(moduleName, options)
    end
end

--{method_appends}
    
return m
