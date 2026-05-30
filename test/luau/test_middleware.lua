local ServerScriptService = game:GetService('ServerScriptService')

local Players = game:GetService('Players')
local player = Players.LocalPlayer

local ClientManifest = require(player.PlayerScripts.Generated.Manifest)
local ServerManifest = require(ServerScriptService.Generated.Manifest)
local RateLimit = require(ServerScriptService.RateLimit)
local Helpers = require('./helpers')

local module = {}

local function createContext(playerName: string)
	return {
		player = {
			Name = playerName,
		},
	}
end

local function loadFixtureManifests()
	Helpers.setupRemotes()
	ServerManifest:loadAllModules()
	ClientManifest:loadAllModules()
	return ClientManifest:getModule('ControllerA')
end

function module.rateLimitBlocksAfterTheWindowQuotaAndResetsAfterTimeout()
	local ok, result
	local playerContext = createContext('RateLimitedMiner')

	for _ = 1, 10 do
		ok, result = RateLimit(playerContext, 'payload')
		assert(ok == true, 'requests inside the quota should be allowed')
		assert(result == 'payload', 'allowed requests should preserve their original payload')
	end

	ok, result = RateLimit(playerContext, 'payload')
	assert(ok == false, 'the first request over the quota should be blocked')
	assert(result.status == 'error', 'blocked requests should return the shared error payload')
end

function module.rateLimitTracksEachPlayerIndependently()
	local firstPlayer = createContext('FirstMiner')
	local secondPlayer = createContext('SecondMiner')

	for _ = 1, 11 do
		RateLimit(firstPlayer, 'first')
	end

	local ok, result = RateLimit(secondPlayer, 'second')

	assert(ok == true, 'one player being limited should not affect another player bucket')
	assert(result == 'second', 'independent player requests should preserve their payload')
end

function module.generatedManifestRegistersMiddlewareAnnotation()
	local rateLimitModule = ServerManifest.manifest.modules.RateLimit
	assert(rateLimitModule ~= nil)

	local middleware = rateLimitModule.annotations.RateLimit
	assert(middleware ~= nil)
	assert(#middleware == 1)
	assert(middleware[1].name == 'middleware')
	assert(middleware[1].args[1] == 'server')
	assert(middleware[1].args[2] == 'inbound')
	assert(middleware[1].kwargs.global == true)
	assert(middleware[1].data.middleware_name == 'RateLimit')
end

function module.generatedMiddlewareAllowsRemoteRequestsWithinQuota()
	local controller = loadFixtureManifests()

	for _ = 1, 10 do
		assert(controller.ping() == 'pong')
	end
end

function module.generatedMiddlewareBlocksTheEleventhRemoteRequest()
	local controller = loadFixtureManifests()

	for _ = 1, 10 do
		assert(controller.ping() == 'pong')
	end

	local result = controller.ping()
	assert(type(result) == 'table')
	assert(result.status == 'error')
	assert(result.message == 'You are sending requests too quickly.')
end

return module
