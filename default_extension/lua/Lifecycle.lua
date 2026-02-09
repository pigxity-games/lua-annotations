local serviceMap: {[string]: any} = {}
local services: {any} = {}

--@onPostInit
function _postInit()
    for i, service in ipairs(services) do
        local module = service.module
        local deps: {string} = service.kwargs.deps

        if module._init then
            --build deps list
            local inject_deps = {}
            if deps then
                for i, dep in ipairs(deps) do
                    table.insert(inject_deps, serviceMap[dep])
                end
            end

            module._init(deps)
        end
    end
end

--@annotationInit
function _service(anot)
    --preserve load order
    table.insert(services, anot)
    serviceMap[anot.module_name] = anot
end