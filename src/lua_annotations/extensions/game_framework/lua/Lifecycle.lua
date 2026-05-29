local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local isServer = RunService:IsServer()
local isStudio = RunService:IsStudio()
local remoteTargetEnv = if isServer then "client" else "server"
local currentEnv = if isServer then "server" else "client"
local componentInstances = {}
local remoteInfoByEnv = {}
local NO_CLEANUP = {}
local middlewareRegistry = {
	inbound = {
		global = {},
		named = {},
	},
	outbound = {
		global = {},
		named = {},
	},
}


local function log(message)
	if isStudio then
		print("[LuaAnnotations] " .. message)
	end
end


local function unpackPacked(args)
	return table.unpack(args, 1, args.n)
end


local function packTail(args)
	return table.pack(table.unpack(args, 2, args.n))
end


local function tailUnpack(args)
	return table.unpack(args, 2, args.n)
end


local function splitFirst(...)
	local args = table.pack(...)
	return args[1], packTail(args)
end


local function isRemoteEvent(remote: RemoteFunction | RemoteEvent | UnreliableRemoteEvent)
	return remote:IsA('RemoteEvent') or remote:IsA('UnreliableRemoteEvent')
end


local function getRemoteType(remote: RemoteFunction | RemoteEvent | UnreliableRemoteEvent)
	if remote:IsA('RemoteFunction') then
		return 'function'
	elseif remote:IsA('UnreliableRemoteEvent') then
		return 'unreliable'
	end

	return 'event'
end


local function getRemoteInfo(env, serviceName, methodName, fallbackType)
	local envInfo = remoteInfoByEnv[env]
	local serviceInfo = envInfo and envInfo[serviceName]
	local remoteInfo = serviceInfo and serviceInfo[methodName]

	if remoteInfo then
		return remoteInfo
	end

	return {
		service = serviceName,
		method = methodName,
		remoteType = fallbackType,
		middleware = {},
	}
end


local function getRemoteInfoFromAnnotation(anot)
	return {
		service = anot.data.remote_parent,
		method = anot.data.remote_name,
		remoteType = anot.args[1],
		middleware = anot.kwargs.middleware or {},
	}
end


local function makeRemoteContext(remoteInfo, direction, player)
	return {
		player = player,
		direction = direction,
		service = remoteInfo.service,
		method = remoteInfo.method,
		remoteType = remoteInfo.remoteType,
	}
end


local function appendMiddleware(chain, added, data)
	if not data or added[data.name] then
		return
	end

	added[data.name] = true
	table.insert(chain, data.callback)
end


local function resolveMiddlewareChain(remoteInfo, direction)
	local registry = middlewareRegistry[direction]
	local chain = {}
	local added = {}

	for _, data in ipairs(registry.global) do
		appendMiddleware(chain, added, data)
	end

	for _, name in ipairs(remoteInfo.middleware or {}) do
		appendMiddleware(chain, added, registry.named[name])
	end

	return chain
end


local function runMiddlewareChain(chain, ctx, ...)
	local args = table.pack(...)

	for _, callback in ipairs(chain) do
		local result = table.pack(callback(ctx, unpackPacked(args)))

		if result[1] ~= true then
			return false, tailUnpack(result)
		end

		args = packTail(result)
	end

	return true, unpackPacked(args)
end


local function runRemoteMiddleware(chain, remoteInfo, direction, player, ...)
	local ctx = makeRemoteContext(remoteInfo, direction, player)
	return table.pack(runMiddlewareChain(chain, ctx, ...))
end


local function makeComponentClass<T>(class: T, dataGetter: (any) -> ())
	class.__index = class 

	function class.new(inst, deps)
		local self = setmetatable(dataGetter and dataGetter(inst) or {}, class)
		if class._init then
			class._init(self, inst, deps)
		end
		return self
	end
end


local function useCollectionTag(tag, consumer)
	local cleanups = setmetatable({}, { __mode = "k" })
	local t0 = os.clock()

	local function onAdd(inst)
		--dedupe
		if cleanups[inst] ~= nil then
			return
		end

		--TODO: ensure component does not already exist for inst

		local cleanup = consumer(inst)
		if cleanup then
			cleanups[inst] = cleanup
		else
			cleanups[inst] = NO_CLEANUP
		end
	end

	local function onRemove(inst)
		local cleanup = cleanups[inst]
		if cleanup then
			if cleanup ~= NO_CLEANUP then
				cleanup()
			end
			cleanups[inst] = nil
		end
	end

	CollectionService:GetInstanceAddedSignal(tag):Connect(onAdd)
	CollectionService:GetInstanceRemovedSignal(tag):Connect(onRemove)

	for _, inst in ipairs(CollectionService:GetTagged(tag)) do
		onAdd(inst)
	end

	log("bound tag " .. tag .. " in " .. (os.clock() - t0) .. "s")
end


local function getMainTagForDependency(manifest, depName)
	local depData = manifest.services.entries[depName]
	assert(depData, ("[LuaAnnotations] Unknown component dependency %q"):format(depName))
	assert(depData.tags and depData.tags[1], ("[LuaAnnotations] Dependency %q has no tags"):format(depName))
	return depData.tags[1]
end


local function initService(manifest, data, serviceName, service, baseDeps)
	--services
	if data.kind == "service" then
		if service._init then
			service._init(baseDeps)
		end
		return
		
	--initService
	elseif data.kind == "initService" then
		service(baseDeps)
		return
	end

	local mainTag = assert(data.tags[1], ("[LuaAnnotations] No tags for component %q"):format(serviceName))

	--convert component to class; handle data_service
	local getComponentData
	local dataService
	if data.data_service then
		dataService = manifest.services.entries[data.data_service].getAdornee()

		getComponentData = function(inst) 
			local state = dataService[inst]
			if not state then
				state = {}
				dataService[inst] = state
			end
			return state
		end

		--initialize any component declarations
		for inst, _ in pairs(dataService) do
			inst:AddTag(mainTag)
		end
	end

	makeComponentClass(service, getComponentData)

	local instances = componentInstances[serviceName]
	if not instances then
		instances = setmetatable({}, { __mode = "k" })
		componentInstances[serviceName] = instances
	end

	--bind CollectionService tags
	for _, tag in ipairs(data.tags) do
		local componentDeps = data.depends.components
		local hasComponentDeps = #componentDeps > 0

		useCollectionTag(tag, function(inst)
			local deps = hasComponentDeps and table.clone(baseDeps) or baseDeps
			local createdDepTags = hasComponentDeps and {} or nil

			--inject component deps
			for _, dep in ipairs(componentDeps) do
				local depInstances = componentInstances[dep]
				local depObj = depInstances and depInstances[inst]
				
				if not depObj then
					local depTag = getMainTagForDependency(manifest, dep)

					if not inst:HasTag(depTag) then
						--create dep if it doesn't exist
						inst:AddTag(depTag)
						assert(createdDepTags)
						createdDepTags[dep] = depTag
					end

					--try again after creating instance
					depInstances = componentInstances[dep]
					depObj = depInstances and depInstances[inst]

					--error if failed twice
					assert(depObj, ("[LuaAnnotations] Failed to resolve dependency %q for %q"):format(dep, serviceName))
				end
				
				deps[dep] = depObj
			end

			--create component
			local obj = service.new(inst, deps)
			instances[inst] = obj

			return function()
				instances[inst] = nil

				--destroy component
				if obj._destroy then
					obj:_destroy()
				end

				--destroy any dependencies as well
				if createdDepTags then
					for _, depTag in pairs(createdDepTags) do
						if inst:HasTag(depTag) then
							inst:RemoveTag(depTag)
						end
					end
				end

				--remove from registry
				if dataService then
					dataService[inst] = nil
				end
			end
		end)
	end
end


local remoteRoot = ReplicatedStorage:WaitForChild('Generated'):WaitForChild('Remotes')
local remoteCache = {}


local function fireServerRemote(remote: RemoteEvent | UnreliableRemoteEvent, ...)
	remote:FireServer(...)
end


local function fireClientRemote(remote: RemoteEvent | UnreliableRemoteEvent, player, ...)
	if player == 'all' then
		remote:FireAllClients(...)
	elseif typeof(player) == 'table' then
		for _, plr in ipairs(player) do
			remote:FireClient(plr, ...)
		end
	else
		remote:FireClient(player, ...)
	end
end


local function runOutboundMiddleware(chain, remoteInfo, ...)
	local player
	local args

	if isServer then
		player, args = splitFirst(...)
	else
		args = table.pack(...)
	end

	local ctx = makeRemoteContext(remoteInfo, 'outbound', player)
	local result = table.pack(runMiddlewareChain(chain, ctx, unpackPacked(args)))
	return result, player
end


local function createEventSender(remote: RemoteEvent | UnreliableRemoteEvent)
	if isServer then
		return function(player, ...)
			fireClientRemote(remote, player, ...)
		end
	else
		return function(...)
			fireServerRemote(remote, ...)
		end
	end
end


local function createMiddlewareEventSender(remoteInfo, remote: RemoteEvent | UnreliableRemoteEvent, chain)
	return function(...)
		local result, player = runOutboundMiddleware(chain, remoteInfo, ...)
		if result[1] ~= true then
			return
		end

		if isServer then
			return fireClientRemote(remote, player, tailUnpack(result))
		end

		return fireServerRemote(remote, tailUnpack(result))
	end
end


local function createFunctionSender(remote: RemoteFunction)
	if isServer then
		return function(player, ...)
			return remote:InvokeClient(player, ...)
		end
	else
		return function(...)
			return remote:InvokeServer(...)
		end
	end
end


local function createMiddlewareFunctionSender(remoteInfo, remote: RemoteFunction, chain)
	return function(...)
		local result, player = runOutboundMiddleware(chain, remoteInfo, ...)
		if result[1] ~= true then
			return tailUnpack(result)
		end

		if isServer then
			return remote:InvokeClient(player, tailUnpack(result))
		end

		return remote:InvokeServer(tailUnpack(result))
	end
end


local function createRemoteSender(remoteInfo, remote: RemoteFunction | RemoteEvent | UnreliableRemoteEvent)
	local chain = resolveMiddlewareChain(remoteInfo, 'outbound')

	if #chain == 0 then
		if isRemoteEvent(remote) then
			return createEventSender(remote)
		end

		return createFunctionSender(remote)
	end

	if isRemoteEvent(remote) then
		return createMiddlewareEventSender(remoteInfo, remote, chain)
	end

	return createMiddlewareFunctionSender(remoteInfo, remote, chain)
end


local function getRemoteTable(folderName)
	local cached = remoteCache[folderName]
	if cached then
		return cached
	end

	local serviceInfo = assert(
		remoteInfoByEnv[remoteTargetEnv] and remoteInfoByEnv[remoteTargetEnv][folderName],
		("[LuaAnnotations] Unknown remote service %q for %s"):format(folderName, remoteTargetEnv)
	)

	local folder = remoteRoot:WaitForChild(folderName)
	local remotesTable = {}

	for remoteName, remoteInfo in pairs(serviceInfo) do
		local remote = folder:WaitForChild(remoteName)
		remotesTable[remoteName] = createRemoteSender(remoteInfo, remote)
	end

	remoteCache[folderName] = remotesTable
	return remotesTable
end


--@annotationInit
function bindTag(anot)
	local adornee = anot.getAdornee()

	for _, tag in ipairs(anot.args[1]) do
		useCollectionTag(tag, adornee)
	end
end


--@annotationInit
function middleware(anot)
	local env = anot.args[1]
	if env ~= currentEnv then
		return
	end

	local direction = anot.args[2]
	local registry = middlewareRegistry[direction]
	assert(registry, ('[LuaAnnotations] Unknown middleware direction %q'):format(direction))

	local data = {
		name = anot.data.middleware_name,
		callback = anot.getAdornee(),
	}

	registry.named[data.name] = data

	if anot.kwargs.global == true then
		table.insert(registry.global, data)
	end
end


--@onPostInit
function initServices(manifest)
	remoteInfoByEnv = manifest.remotes or {}

	local t0 = os.clock()
	local remoteT0 = os.clock()
	local remoteDepCount = 0
	for _, serviceName in ipairs(manifest.services.load_order) do
		local data = manifest.services.entries[serviceName]
		local service = data.getAdornee()

		--build deps list
		local injectDeps = {}
		injectDeps[remoteTargetEnv] = {}

		--service deps
		for _, dep in ipairs(data.depends.services) do
			injectDeps[dep] = manifest.services.entries[dep].getAdornee()
		end

		--remote deps
		for _, dep in ipairs(data.depends.remotes) do
			injectDeps[remoteTargetEnv][dep] = getRemoteTable(dep)
			remoteDepCount += 1
		end

		initService(manifest, data, serviceName, service, injectDeps)
	end

	log("game-framework " .. currentEnv .. " services started in " .. (os.clock() - t0) .. "s (remote_deps=" .. remoteDepCount .. ", remote_setup=" .. (os.clock() - remoteT0) .. "s)")
end


--@annotationInit
function remote(anot)
	local t0 = os.clock()
	local callback = anot.getAdornee()
	local remoteInfo = getRemoteInfoFromAnnotation(anot)
	local anotType = remoteInfo.remoteType --event, unreliable, or function
	local remote = remoteRoot[anot.data.remote_parent]:WaitForChild(anot.data.remote_name)

	local wrappedCallback
	wrappedCallback = function(...)
		local chain = resolveMiddlewareChain(remoteInfo, 'inbound')
		if #chain == 0 then
			wrappedCallback = callback
			return callback(...)
		end

		wrappedCallback = function(...)
			local player
			local args

			if isServer then
				player, args = splitFirst(...)
			else
				args = table.pack(...)
			end

			local result = runRemoteMiddleware(chain, remoteInfo, 'inbound', player, unpackPacked(args))

			if result[1] ~= true then
				if remoteInfo.remoteType == 'function' then
					return tailUnpack(result)
				end

				return
			end

			if isServer then
				return callback(player, tailUnpack(result))
			end

			return callback(tailUnpack(result))
		end

		return wrappedCallback(...)
	end

	if anotType == 'event' or anotType == 'unreliable' then
		assert(isRemoteEvent(remote), '[LuaAnnotations] Expected RemoteEvent')
		if isServer then
			remote.OnServerEvent:Connect(function(...)
				return wrappedCallback(...)
			end)
		else
			remote.OnClientEvent:Connect(function(...)
				return wrappedCallback(...)
			end)
		end
	else
		assert(remote:IsA('RemoteFunction'), '[LuaAnnotations] Expected RemoteFunction')
		if isServer then
			remote.OnServerInvoke = function(...)
				return wrappedCallback(...)
			end
		else
			remote.OnClientInvoke = function(...)
				return wrappedCallback(...)
			end
		end
	end

	log("bound remote " .. remoteInfo.service .. "." .. remoteInfo.method .. " in " .. (os.clock() - t0) .. "s")
end


return {
	initServices = initServices,
	bindTag = bindTag,
	middleware = middleware,
	remote = remote,
}
