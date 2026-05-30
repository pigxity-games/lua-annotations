local CollectionService = game:GetService('CollectionService')
local ReplicatedStorage = game:GetService('ReplicatedStorage')
local RunService = game:GetService('RunService')

local isStudio = RunService:IsStudio()
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

local remoteRoot = ReplicatedStorage:WaitForChild('Generated'):WaitForChild('Remotes')


local function getCurrentEnv(manifestApi)
	return manifestApi.environment
end


local function getRemoteTargetEnv(manifestApi)
	return if getCurrentEnv(manifestApi) == 'server' then 'client' else 'server'
end


local function isManifestServer(manifestApi)
	return getCurrentEnv(manifestApi) == 'server'
end


local function log(message)
	if isStudio then
		print('[LuaAnnotations] ' .. message)
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


local function getRemoteInfo(manifestApi, env, serviceName, methodName, fallbackType)
	local envInfo = manifestApi.manifest.remotes[env]
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


local function getAnnotationAdornee(manifestApi, moduleName, methodName)
	local module = manifestApi:getCached(moduleName)
	if methodName == '_module' or type(module) ~= 'table' then
		return module
	end

	return module[methodName]
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


local function runOutboundMiddleware(manifestApi, chain, remoteInfo, ...)
	local player
	local args

	if isManifestServer(manifestApi) then
		player, args = splitFirst(...)
	else
		args = table.pack(...)
	end

	local ctx = makeRemoteContext(remoteInfo, 'outbound', player)
	local result = table.pack(runMiddlewareChain(chain, ctx, unpackPacked(args)))
	return result, player
end


local function createEventSender(manifestApi, remote: RemoteEvent | UnreliableRemoteEvent)
	if isManifestServer(manifestApi) then
		return function(player, ...)
			fireClientRemote(remote, player, ...)
		end
	end

	return function(...)
		fireServerRemote(remote, ...)
	end
end


local function createMiddlewareEventSender(manifestApi, remoteInfo, remote: RemoteEvent | UnreliableRemoteEvent, chain)
	return function(...)
		local result, player = runOutboundMiddleware(manifestApi, chain, remoteInfo, ...)
		if result[1] ~= true then
			return
		end

		if isManifestServer(manifestApi) then
			return fireClientRemote(remote, player, tailUnpack(result))
		end

		return fireServerRemote(remote, tailUnpack(result))
	end
end


local function createFunctionSender(manifestApi, remote: RemoteFunction)
	if isManifestServer(manifestApi) then
		return function(player, ...)
			return remote:InvokeClient(player, ...)
		end
	end

	return function(...)
		return remote:InvokeServer(...)
	end
end


local function createMiddlewareFunctionSender(manifestApi, remoteInfo, remote: RemoteFunction, chain)
	return function(...)
		local result, player = runOutboundMiddleware(manifestApi, chain, remoteInfo, ...)
		if result[1] ~= true then
			return tailUnpack(result)
		end

		if isManifestServer(manifestApi) then
			return remote:InvokeClient(player, tailUnpack(result))
		end

		return remote:InvokeServer(tailUnpack(result))
	end
end


local function createRemoteSender(manifestApi, remoteInfo, remote: RemoteFunction | RemoteEvent | UnreliableRemoteEvent)
	local chain = resolveMiddlewareChain(remoteInfo, 'outbound')

	if #chain == 0 then
		if isRemoteEvent(remote) then
			return createEventSender(manifestApi, remote)
		end

		return createFunctionSender(manifestApi, remote)
	end

	if isRemoteEvent(remote) then
		return createMiddlewareEventSender(manifestApi, remoteInfo, remote, chain)
	end

	return createMiddlewareFunctionSender(manifestApi, remoteInfo, remote, chain)
end


local function getRemoteTable(manifestApi, folderName)
	local cached = manifestApi._remoteCache[folderName]
	if cached then
		return cached
	end

	local remoteTargetEnv = getRemoteTargetEnv(manifestApi)
	local serviceInfo = assert(
		manifestApi.manifest.remotes[remoteTargetEnv] and manifestApi.manifest.remotes[remoteTargetEnv][folderName],
		('[LuaAnnotations] Unknown remote service %q for %s'):format(folderName, remoteTargetEnv)
	)

	local folder = remoteRoot:WaitForChild(folderName)
	local remotesTable = {}

	for remoteName, remoteInfo in pairs(serviceInfo) do
		local remote = folder:WaitForChild(remoteName)
		remotesTable[remoteName] = createRemoteSender(manifestApi, remoteInfo, remote)
	end

	manifestApi._remoteCache[folderName] = remotesTable
	return remotesTable
end


--@moduleInit
function initService(manifestApi, data, serviceName)
	if data == nil or data.kind == 'dependency' then
		return
	end

	manifestApi:startService(serviceName)
end


--@annotationInit
function bindTag(manifestApi, anot, methodName, _, moduleName)
	local adornee = getAnnotationAdornee(manifestApi, moduleName, methodName)

	for _, tag in ipairs(anot.args[1]) do
		manifestApi._useCollectionTag(tag, adornee)
	end
end


--@annotationInit
function middleware(manifestApi, anot, methodName, _, moduleName)
	local env = anot.args[1]
	if env ~= getCurrentEnv(manifestApi) then
		return
	end

	local direction = anot.args[2]
	local registry = middlewareRegistry[direction]
	assert(registry, ('[LuaAnnotations] Unknown middleware direction %q'):format(direction))

	local data = {
		name = anot.data.middleware_name,
		callback = getAnnotationAdornee(manifestApi, moduleName, methodName),
	}

	registry.named[data.name] = data

	if anot.kwargs.global == true then
		table.insert(registry.global, data)
	end
end


--@annotationInit
function remote(manifestApi, anot, methodName, _, moduleName)
	local t0 = os.clock()
	local callback = getAnnotationAdornee(manifestApi, moduleName, methodName)
	local remoteInfo = getRemoteInfoFromAnnotation(anot)
	local anotType = remoteInfo.remoteType
	local remoteInst = remoteRoot[anot.data.remote_parent]:WaitForChild(anot.data.remote_name)

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

			if isManifestServer(manifestApi) then
				player, args = splitFirst(...)
			else
				args = table.pack(...)
			end

			local info = getRemoteInfo(
				manifestApi,
				getCurrentEnv(manifestApi),
				remoteInfo.service,
				remoteInfo.method,
				remoteInfo.remoteType
			)
			local result = runRemoteMiddleware(chain, info, 'inbound', player, unpackPacked(args))

			if result[1] ~= true then
				if info.remoteType == 'function' then
					return tailUnpack(result)
				end

				return
			end

			if isManifestServer(manifestApi) then
				return callback(player, tailUnpack(result))
			end

			return callback(tailUnpack(result))
		end

		return wrappedCallback(...)
	end

	if anotType == 'event' or anotType == 'unreliable' then
		assert(isRemoteEvent(remoteInst), '[LuaAnnotations] Expected RemoteEvent')
		if isManifestServer(manifestApi) then
			remoteInst.OnServerEvent:Connect(function(...)
				return wrappedCallback(...)
			end)
		else
			remoteInst.OnClientEvent:Connect(function(...)
				return wrappedCallback(...)
			end)
		end
	else
		assert(remoteInst:IsA('RemoteFunction'), '[LuaAnnotations] Expected RemoteFunction')
		if isManifestServer(manifestApi) then
			remoteInst.OnServerInvoke = function(...)
				return wrappedCallback(...)
			end
		else
			remoteInst.OnClientInvoke = function(...)
				return wrappedCallback(...)
			end
		end
	end

	log('bound remote ' .. remoteInfo.service .. '.' .. remoteInfo.method .. ' in ' .. (os.clock() - t0) .. 's')
end


return {
	initService = initService,
	bindTag = bindTag,
	middleware = middleware,
	remote = remote,
	getRemoteTable = getRemoteTable,
}
