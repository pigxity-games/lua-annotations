local module = {}

function module.makeClass(class: table)
    class.__index = class

    function class.new(...)
        local self = setmetatable({}, class)
        if class._init then
            class._init(self, ...)
        end
        return self
    end
end

return module