local ReplicatedStorage = game:GetService("ReplicatedStorage")
local class = require(ReplicatedStorage.generated.Index).Class

local TestClass = {}

function TestClass:_init(str: any)
    self.value = str
end

function TestClass:getString(): any
    return self.value
end

return class(TestClass)