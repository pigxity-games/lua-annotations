local ServerScriptService = game:GetService('ServerScriptService')

local ServerManifest = require(ServerScriptService.Generated.Manifest)
local Helpers = require('./helpers')

local module = {}

local function countKeys(map)
	local count = 0
	for _ in pairs(map) do
		count += 1
	end
	return count
end

local function loadServerModules()
	Helpers.loadServerModules(ServerManifest)
end

function module.initServiceIsRegisteredAsFunctionBackedService()
	local moduleInfo = ServerManifest.manifest.modules.runFixtureInit
	assert(moduleInfo ~= nil)
	assert(moduleInfo.data.kind == 'initService')
	assert(ServerManifest:getModule('runFixtureInit') ~= nil)
	assert(type(ServerManifest:getModule('runFixtureInit')) == 'function')
end

function module.initServiceRunsAutomaticallyAndReceivesDependencies()
	Helpers.setupCounterRegistryParts()

	local state = ServerManifest:getModule('InitState')
	assert(state.ran == false)
	assert(state.serviceInjected == false)
	assert(state.serviceWasInitialized == false)
	assert(state.counterRegistryInjected == false)
	assert(state.part1Value == nil)

	loadServerModules()

	assert(state.ran == true, '@initService should run during manifest module initialization')
	assert(state.serviceInjected == true, '@initService should receive normal service dependencies')
	assert(state.serviceWasInitialized == true, 'service dependencies should be initialized before @initService runs')
	assert(state.counterRegistryInjected == true, '@initService should receive dependency modules through deps')
	assert(state.part1Value == 123, 'docs-style registry data should be available from @initService deps')
end

function module.loadAfterAffectsOrderWithoutInjectingTheTargetService()
	local manifest = ServerManifest.manifest
	local moduleInfo = manifest.modules.LoadAfterService
	assert(moduleInfo ~= nil)
	assert(moduleInfo.data.kind == 'service')
	assert(#moduleInfo.data.depends.services == 0, 'load_after should not inject the target service into deps')

	local serviceBIndex = table.find(manifest.load_order, 'ServiceB')
	local loadAfterIndex = table.find(manifest.load_order, 'LoadAfterService')

	assert(serviceBIndex ~= nil)
	assert(loadAfterIndex ~= nil)
	assert(serviceBIndex < loadAfterIndex, 'load_after should place the target earlier in load order')
	assert(table.find(manifest.load_order, 'InitState') == nil, 'dependency modules should not be part of runtime load_order')

	loadServerModules()

	local service = ServerManifest:getModule('LoadAfterService')
	assert(service.initialized == true)
	assert(service.deps ~= nil)
	assert(service.deps.ServiceB == nil, 'load_after should not add ServiceB to deps')
	assert(service.deps.client ~= nil, 'runtime deps should still include the remote environment table')
	assert(countKeys(service.deps) == 1)
end

return module
