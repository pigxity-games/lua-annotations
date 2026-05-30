--@module
local m = {}

--@initService, depends=[ServiceB, InitState, CounterRegistry]
function m.runFixtureInit(deps)
    local state = deps.InitState
    state.ran = true
    state.serviceInjected = deps.ServiceB ~= nil
    state.serviceWasInitialized = deps.ServiceB.initialized == true
    state.counterRegistryInjected = deps.CounterRegistry ~= nil

    local part1 = workspace:FindFirstChild('Part1')
    if part1 then
        local data = deps.CounterRegistry[part1]
        if data then
            state.part1Value = data.val
        end
    end
end

return m
