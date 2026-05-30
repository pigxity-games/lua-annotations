--@module
local m = {}

--@bindTag, SimpleComponent
function m.component(inst)
    local oldName = inst.Name
    inst.Name = 'Component'

    return function()
        inst.Name = oldName
    end
end

return m
