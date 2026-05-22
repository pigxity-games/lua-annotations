local function makeModuleLocator(serviceNameMap)
    return function(workspaceName, serviceName)
        local workspaceModules = assert(
            serviceNameMap[workspaceName],
            ('[lua-anot unit-test] Unknown workspace %q'):format(workspaceName)
        )
        local moduleInfo = assert(
            workspaceModules[serviceName],
            ('[lua-anot unit-test] Unknown dependency %q for workspace %q'):format(serviceName, workspaceName)
        )

        local serviceRoots = {
            shared = game:GetService('ReplicatedStorage'),
            server = game:GetService('ServerScriptService'),
            client = game:GetService('Players').LocalPlayer.PlayerScripts,
        }

        local current = assert(serviceRoots[moduleInfo.env], ('[lua-anot unit-test] Unsupported env %q'):format(moduleInfo.env))
        for _, part in ipairs(moduleInfo.path) do
            current = current[part]
        end

        return require(current), moduleInfo
    end
end


local function makeDependencyBuilder(serviceNameMap)
    local getModule = makeModuleLocator(serviceNameMap)

    return function(workspaceName, requestedServices, skipInit)
        local cache = {}
        local pending = {}

        local function build(serviceName)
            local cached = cache[serviceName]
            if cached ~= nil then
                return cached
            end

            assert(not pending[serviceName], ('[lua-anot unit-test] Cycle detected while building %q'):format(serviceName))
            pending[serviceName] = true

            local moduleValue, moduleInfo = getModule(workspaceName, serviceName)
            local builtDeps = {}

            for _, depName in ipairs(moduleInfo.depends) do
                builtDeps[depName] = build(depName)
            end

            if skipInit ~= true then
                if moduleInfo.kind == 'service' and moduleValue._init then
                    moduleValue._init(builtDeps)
                elseif moduleInfo.kind == 'initService' then
                    moduleValue(builtDeps)
                end
            end

            pending[serviceName] = nil
            cache[serviceName] = moduleValue
            return moduleValue
        end

        local out = {}
        for _, serviceName in ipairs(requestedServices) do
            out[serviceName] = build(serviceName)
        end
        return out
    end
end


local createDependencies = makeDependencyBuilder(--serviceNameMap)

return --manifest
