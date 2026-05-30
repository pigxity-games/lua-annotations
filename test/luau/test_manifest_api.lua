local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")

local Players = game:GetService("Players")
local player = Players.LocalPlayer

local ClientManifest = require(player.PlayerScripts.Generated.Manifest)
local ServerManifest = require(ServerScriptService.Generated.Manifest)
local Helpers = require('./helpers')

local m = {}

function m.sharedServiceInBothManifests()
	local clientManifest = ClientManifest.manifest
	local serverManifest = ServerManifest.manifest

	assert(clientManifest.modules.SharedService ~= nil)
	assert(serverManifest.modules.SharedService ~= nil)
end

function m.sharedGeneratedStructure()
	local generated = ReplicatedStorage.Generated
	assert(generated:FindFirstChild("Manifest") == nil)
	assert(generated["_Internal"].Lifecycle ~= nil)
end


-- // CORE MANIFEST API //

function m.coreGetModule()
	local SharedService = ServerManifest:getModule("SharedService")
	assert(SharedService.initialized == false)
	assert(SharedService.add(1,2) == 3)
end

function m.coreLoadModule()
	local module = ClientManifest:loadModule("SharedService") --runs all annotation handlers or module handlers; here, it should start the service.
	assert(module.initialized == true)
end


-- // GAME-FRAMEWORK API //

function m.controllerAPingReturnsPong()
    Helpers.setupRemotes()
    ServerManifest:startService("ServiceA")

    local Controller = ClientManifest:startService("ControllerA")
    assert(Controller.ping() == "pong")
end

function m.getServiceDepsControllerA()	
	Helpers.setupRemotes()
	local deps = ClientManifest:getServiceDeps("ControllerA")
	assert(deps.server.ServiceA ~= nil)

	ServerManifest:startService("ServiceA")
	assert(deps.server.ServiceA.pingRemote() == "pong")
end

function m.getServiceDepsWithoutInitializing()
	local deps = ServerManifest:getServiceDeps("ServiceA", false)
	assert(deps.ServiceB.initialized == false)
end

function m.startServiceCustomDeps()
	local ran = false

	local controller = ClientManifest:startService("ControllerA", {
		server = {
			ServiceA = {
				pingRemote = function()
					ran = true
					return "hello"
				end
			}
		}
	})

	assert(controller.ping() == "hello")
	assert(ran == true)
end

return m
