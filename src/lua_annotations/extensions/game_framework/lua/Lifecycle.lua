local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local isServer = RunService:IsServer()
local remoteTargetEnv = if isServer then "client" else "server"
local currentEnv = if isServer then "server" else "client"
local componentInstances = {}
local remoteInfoByEnv = {}
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


local function unpackPacked(args)
	return table.unpack(args, 1, args.n)
end


local function packTail(args)
	return table.pack(table.unpack(args, 2, args.n))
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
			return false, table.unpack(result, 2, result.n)
		end

		args = packTail(result)
	end

	return true, unpackPacked(args)
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

	local function onAdd(inst)
		--dedupe
		if cleanups[inst] ~= nil then
			return
		end

		--TODO: ensure component does not already exist for inst

		local cleanup = consumer(inst)
		if cleanup then
			cleanups[inst] = cleanup
		end
	end

	local function onRemove(inst)
		if cleanups[inst] then
			cleanups[inst]()
			cleanups[inst] = nil
		end
	end

	CollectionService:GetInstanceAddedSignal(tag):Connect(onAdd)
	CollectionService:GetInstanceRemovedSignal(tag):Connect(onRemove)

	for _, inst in ipairs(CollectionService:GetTagged(tag)) do
		onAdd(inst)
	end
end


local function getMainTagForDependency(manifest, depName)
	local depData = manifest.services.entries[depName]
	assert(depData, ("Unknown component dependency %q"):format(depName))
	assert(depData.tags and depData.tags[1], ("Dependency %q has no tags"):format(depName))
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

	local mainTag = assert(data.tags[1], ("No tags for component %q"):format(serviceName))

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
					assert(depObj, ("Failed to resolve dependency %q for %q"):format(dep, serviceName))
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


local function createEventSender(remoteInfo, remote: RemoteEvent | UnreliableRemoteEvent, remoteTable, remoteName)
	local sender

	if isServer then
		sender = function(player, ...)
			fireClientRemote(remote, player, ...)
		end
	else
		sender = function(...)
			fireServerRemote(remote, ...)
		end
	end

	local wrapped
	wrapped = function(...)
		local chain = resolveMiddlewareChain(remoteInfo, 'outbound')
		if #chain == 0 then
			remoteTable[remoteName] = sender
			return sender(...)
		end

		local middlewareSender = function(...)
			local result, player = runOutboundMiddleware(chain, remoteInfo, ...)
			if result[1] ~= true then
				return
			end

			if isServer then
				return fireClientRemote(remote, player, table.unpack(result, 2, result.n))
			end

			return fireServerRemote(remote, table.unpack(result, 2, result.n))
		end

		remoteTable[remoteName] = middlewareSender
		return middlewareSender(...)
	end

	return wrapped
end


local function createFunctionSender(remoteInfo, remote: RemoteFunction, remoteTable, remoteName)
	local sender

	if isServer then
		sender = function(player, ...)
			return remote:InvokeClient(player, ...)
		end
	else
		sender = function(...)
			return remote:InvokeServer(...)
		end
	end

	local wrapped
	wrapped = function(...)
		local chain = resolveMiddlewareChain(remoteInfo, 'outbound')
		if #chain == 0 then
			remoteTable[remoteName] = sender
			return sender(...)
		end

		local middlewareSender = function(...)
			local result, player = runOutboundMiddleware(chain, remoteInfo, ...)
			if result[1] ~= true then
				return table.unpack(result, 2, result.n)
			end

			if isServer then
				return remote:InvokeClient(player, table.unpack(result, 2, result.n))
			end

			return remote:InvokeServer(table.unpack(result, 2, result.n))
		end

		remoteTable[remoteName] = middlewareSender
		return middlewareSender(...)
	end

	return wrapped
end


local function createRemoteSender(remoteInfo, remote: RemoteFunction | RemoteEvent | UnreliableRemoteEvent, remoteTable, remoteName)
	if isRemoteEvent(remote) then
		return createEventSender(remoteInfo, remote, remoteTable, remoteName)
	end

	return createFunctionSender(remoteInfo, remote, remoteTable, remoteName)
end


local function getRemoteTable(folderName)
	--cache remotes by service name
	local cached = remoteCache[folderName]
	if cached then
		return cached
	end

	--wrap remote events into a table that is similar to a service
	local folder = remoteRoot:WaitForChild(folderName)
	local remotesTable = {}

	for _, remote in ipairs(folder:GetChildren()) do
		local remoteInfo = getRemoteInfo(remoteTargetEnv, folderName, remote.Name, getRemoteType(remote))
		remotesTable[remote.Name] = createRemoteSender(remoteInfo, remote, remotesTable, remote.Name)
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
	assert(registry, ('Unknown middleware direction %q'):format(direction))

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
		end

		initService(manifest, data, serviceName, service, injectDeps)
	end

	print("[LuaAnnotations] game-framework " .. currentEnv .. " services started in " .. os.clock() - t0 .. "s")
end


--@annotationInit
function remote(anot)
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

			local ctx = makeRemoteContext(remoteInfo, 'inbound', player)
			local result = table.pack(runMiddlewareChain(chain, ctx, unpackPacked(args)))

			if result[1] ~= true then
				if remoteInfo.remoteType == 'function' then
					return table.unpack(result, 2, result.n)
				end

				return
			end

			if isServer then
				return callback(player, table.unpack(result, 2, result.n))
			end

			return callback(table.unpack(result, 2, result.n))
		end

		return wrappedCallback(...)
	end

	if anotType == 'event' or anotType == 'unreliable' then
		assert(isRemoteEvent(remote), 'Expected RemoteEvent')
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
		assert(remote:IsA('RemoteFunction'), 'Expected RemoteFunction')
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
end


return {
	initServices = initServices,
	bindTag = bindTag,
	middleware = middleware,
	remote = remote,
}
