local ReplicatedStorage = game:GetService("ReplicatedStorage")
local class = require(ReplicatedStorage.Generated.Index).Class

--@class
local TestClass = {}

function TestClass:_init(str: string)
    self.value = str
end

function TestClass:getString()
    return self.value
end

return class(TestClass)