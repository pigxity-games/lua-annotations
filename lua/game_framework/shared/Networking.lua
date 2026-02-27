local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local isServer = RunService:IsServer()


--@module
local module = {}


--@annotationInit
function module.remote(anot)
    local callback = anot.getAdornee()
    local anotType = anot.args[1] --event or function
    local remote = ReplicatedStorage.Generated.Remotes[anot.remote_parent]:WaitForChild(anot.remote_name)

    if anotType == "event" then
        if isServer then
            remote.OnServerEvent:connect(callback)
        else
            remote.OnClientEvent:connect(callback)
        end
    else
        if isServer then
            remote.OnServerInvoke = callback
        else
            remote.OnClientInvoke = callback
        end
    end
end


return module