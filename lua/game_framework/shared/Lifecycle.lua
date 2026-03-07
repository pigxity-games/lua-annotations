local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local class = require(script.Parent.Utils.class)

local isServer = RunService:IsServer()
local oppositeEnvName = isServer and "client" or "server"
local componentInstances = {}


local function useCollectionTag(tag, consumer)
	local cleanups = {}

	local function onAdd(inst)
		--dedupe
		if cleanups[inst] ~= nil then
			return
		end

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


local function initService(manifest, data, serviceName, service, injectDeps)
	if data.kind == "service" then
		service._init(injectDeps)
		return
	end

	--convert component to class; handle data_service
	local componentData = {}
	if data.data_service then
		componentData = manifest.services[data.data_service].getAdornee()
	end
	class(service, componentData)

	local instances = componentInstances[serviceName]
	if instances == nil then
		instances = {}
		componentInstances[serviceName] = instances
	end

	--bind CollectionService tags
	for _, tag in ipairs(data.tags) do
		useCollectionTag(tag, function(inst)
			local deps = table.clone(injectDeps)

			--inject component deps
			for _, dep in ipairs(data.depends.components) do
				local depInstances = componentInstances[dep]
				local toInject = depInstances and depInstances[inst]
				if toInject then
					injectDeps[dep] = toInject
				else
					error(
						string.format(
							"No `%s` component currently exists for instance; component `%s` requires it as a dependency.",
							dep,
							serviceName
						)
					)
				end
			end

			--create component
			local obj = service.new(inst, deps)
			instances[inst] = obj
			return function()
				instances[inst] = nil
				if obj._destroy then
					obj:_destroy()
				end
			end
		end)
	end
end


local function getRemoteMethod(remote: RemoteFunction | RemoteEvent)
	if remote:IsA("RemoteEvent") then
		if isServer then
			return remote.FireClient
		else
			return remote.FireServer
		end
	else
		if isServer then
			return remote.InvokeClient
		else
			return remote.InvokeServer
		end
	end
end


--@module
local module = {}


--@annotationInit
function module.bindTag(anot)
	local adornee = anot.getAdornee()

	for _, tag in ipairs(anot.args[1]) do
		useCollectionTag(tag, adornee)
	end
end


--@onInit
function module.initServices(manifest)
	for _, serviceName in ipairs(manifest.load_order) do
		local data = manifest.services[serviceName]
		local service = data.getAdornee()

		if service._init then
			--build deps list
			if #data.depends.services > 0 or #data.depends.remotes > 0 then
				local injectDeps = {}
				injectDeps[oppositeEnvName] = {}

				--service deps
				for _, dep in ipairs(data.depends.services) do
					injectDeps[dep] = manifest.services[dep].getAdornee()
				end

				--remote deps
				for _, dep in ipairs(data.depends.remotes) do
					--wrap remote events into a table that is similar to a service
					local remotesTable = {}
					local remotes = ReplicatedStorage.Generated.Remotes:WaitForChild(dep)

					for i, remote in ipairs(remotes:GetChildren()) do
						local remoteMethod = getRemoteMethod(remote)

						remotesTable[remote.Name] = function(...)
							return remoteMethod(remote, ...)
						end
					end

					injectDeps[oppositeEnvName][dep] = remotesTable
				end

				initService(manifest, data, serviceName, service, injectDeps)
			else
				initService(manifest, data, serviceName, service, {})
			end
		end
	end
end


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
