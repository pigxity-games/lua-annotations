local ReplicatedStorage = game:GetService("ReplicatedStorage")

type Exports = {
    TableUtils: typeof(require(ReplicatedStorage.Utils.Table)),
    InstanceUtils: typeof(require(ReplicatedStorage.Utils.Instance)),
}

local paths = {
    TableUtils = function() return require(ReplicatedStorage.Utils.Table) end,
    InstanceUtils = function() return require(ReplicatedStorage.Utils.Instance) end,
}

local proxy = setmetatable({}, {
    __index = function(self, key: string)
        local module = paths[key]()
        rawset(self, key, module)
        return module
    end
})

return proxy :: Exports