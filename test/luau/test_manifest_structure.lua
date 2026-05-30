local Players = game:GetService("Players")
local player = Players.LocalPlayer

local ClientManifest = require(player.PlayerScripts.Generated.Manifest)
local manifest = ClientManifest.manifest
local m = {}

local function countKeys(map)
	local count = 0
	for _ in pairs(map) do
		count += 1
	end
	return count
end

function m.hooksAreRegistered()
    assert(manifest.hooks.module_handlers[1].module == "Lifecycle")
    assert(manifest.hooks.module_handlers[1].method == "initService")

    assert(manifest.hooks.annotation_handlers.remote.module == "Lifecycle")
    assert(manifest.hooks.annotation_handlers.remote.method == "remote")
end

function m.onlyControllerAExistsAsModule()
	assert(countKeys(manifest.modules) == 2) -- SharedService inlcuded
	assert(manifest.modules.ControllerA ~= nil)
    assert(manifest.modules.SharedService ~= nil)
end

function m.controllerAIsAService()
	local moduleInfo = manifest.modules.ControllerA

	assert(moduleInfo.data.kind == "service")
    assert(moduleInfo.annotations._module == nil) --@service is actually a build-time annotation, even if it mutates the manifest
end

function m.controllerADependsOnServerServiceA()
	local moduleInfo = manifest.modules.ControllerA

	assert(#moduleInfo.data.depends.services == 0)
	assert(#moduleInfo.data.depends.remotes == 1)
    assert(moduleInfo.data.depends.remotes[1] == "ServiceA")

    assert(moduleInfo.annotations.ping == nil)
    assert(moduleInfo.annotations._init == nil)
end

function m.loadOrderContainsControllerAAndSharedService()
	assert(#manifest.load_order == 2)
    assert(table.find(manifest.load_order, "ControllerA"))
    assert(table.find(manifest.load_order, "SharedService"))
end

return m
