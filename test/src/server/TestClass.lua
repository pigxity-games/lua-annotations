local ServerScriptService = game:GetService("ServerScriptService")
local T = require(ServerScriptService.generated.Types)

--@class
local TestClass = {}

function TestClass:_init(str: string)
    self.value = str
    self._privateProperty = "private!"
end

function TestClass:getString()
    return self.value
end

return TestClass :: T.TestClass