--!strict
-- Exercises manifest loading and injection through generated service contracts.
-- Literal service names identify the generated contract of each opaque registry result.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")

local Players = game:GetService("Players")
local player = Players.LocalPlayer

local ClientManifest = require(player.PlayerScripts.Generated.Manifest)
local ServerManifest = require(ServerScriptService.Generated.Manifest)
local Helpers = require("./helpers")
local ClientServiceTypes = require(player.PlayerScripts.Generated.ServiceTypes)
local ServerServiceTypes = require(ServerScriptService.Generated.ServiceTypes)
local SharedServiceTypes = require(ReplicatedStorage.Generated.ServiceTypes)

local m = {}

function m.sharedServiceInBothManifests()
	local clientManifest = ClientManifest.manifest
	local serverManifest = ServerManifest.manifest

	assert(clientManifest.modules.SharedService ~= nil, "shared service should exist in client manifest")
	assert(serverManifest.modules.SharedService ~= nil, "shared service should exist in server manifest")
end

function m.sharedGeneratedStructure()
	local generated = ReplicatedStorage.Generated
	assert(generated:FindFirstChild("Manifest") == nil, "shared tree should not duplicate Manifest")
	assert(generated["_Internal"].Lifecycle ~= nil, "shared runtime should include Lifecycle")
end

-- // CORE MANIFEST API //

function m.coreGetModule()
	local SharedService = ServerManifest:getModule("SharedService") :: SharedServiceTypes.SharedService
	assert(SharedService.initialized == false, "getModule should not initialize service")
	assert(SharedService.add(1, 2) == 3, "shared add should return numeric sum")
end

function m.coreLoadModule()
	local module = ClientManifest:loadModule("SharedService") :: SharedServiceTypes.SharedService --runs all annotation handlers or module handlers; here, it should start the service.
	assert(module.initialized == true, "loadModule should initialize service")
end

-- // GAME-FRAMEWORK API //

function m.controllerAPingReturnsPong()
	Helpers.setupRemotes()
	ServerManifest:startService("ServiceA")

	local Controller = ClientManifest:startService("ControllerA") :: ClientServiceTypes.ControllerA
	assert(Controller.ping() == "pong", "controller should call remote service")
end

function m.getServiceDepsControllerA()
	Helpers.setupRemotes()
	local deps = ClientManifest:getServiceDeps("ControllerA") :: ClientServiceTypes.ControllerADeps
	assert(deps.server.ServiceA ~= nil, "controller dependency should include ServiceA")

	ServerManifest:startService("ServiceA")
	assert(deps.server.ServiceA.pingRemote() == "pong", "remote dependency should return pong")
end

function m.getServiceDepsWithoutInitializing()
	local deps = ServerManifest:getServiceDeps("ServiceA", false) :: ServerServiceTypes.ServiceADeps
	assert(deps.ServiceB.initialized == false, "dependency lookup should preserve uninitialized service")
end

function m.startServiceCustomDeps()
	local ran = false

	local controller = ClientManifest:startService("ControllerA", {
		server = {
			ServiceA = {
				pingRemote = function()
					ran = true
					return "hello"
				end,
			},
		},
	}) :: ClientServiceTypes.ControllerA

	assert(controller.ping() == "hello", "custom dependency should return hello")
	assert(ran == true, "custom dependency should run")
end

return m
