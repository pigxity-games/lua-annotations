local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local isServer = RunService:IsServer()
local remoteTargetEnv = isServer and "client" or "server"
local currentEnv = isServer and "server" or "client"
local componentInstances = {}


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
	local depData = manifest.services[depName]
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
		dataService = manifest.services[data.data_service].getAdornee()

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
		useCollectionTag(tag, function(inst)
			local deps = table.clone(baseDeps)
			local createdDepTags = {}

			--inject component deps
			for _, dep in ipairs(data.depends.components) do
				local depInstances = componentInstances[dep]
				local depObj = depInstances and depInstances[inst]
				
				if not depObj then
					local depTag = getMainTagForDependency(manifest, dep)

					if not inst:HasTag(depTag) then
						--create dep if it doesn't exist
						inst:AddTag(depTag)
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
				for _, depTag in pairs(createdDepTags) do
					if inst:HasTag(depTag) then
						inst:RemoveTag(depTag)
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


local remoteRoot = ReplicatedStorage:WaitForChild("Generated"):WaitForChild("Remotes")
local remoteCache = {}


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
		local remoteMethod = getRemoteMethod(remote)
		remotesTable[remote.Name] = function(...)
			return remoteMethod(remote, ...)
		end
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


--@onPostInit
function initServices(manifest)
	t0 = os.clock()
	for _, serviceName in ipairs(manifest.load_order) do
		local data = manifest.services[serviceName]
		local service = data.getAdornee()

		--build deps list
		local injectDeps = {}
		injectDeps[remoteTargetEnv] = {}

		--service deps
		for _, dep in ipairs(data.depends.services) do
			injectDeps[dep] = manifest.services[dep].getAdornee()
		end

		--remote deps
		for _, dep in ipairs(data.depends.remotes) do
			injectDeps[remoteTargetEnv][dep] = getRemoteTable(dep)
		end

		initService(manifest, data, serviceName, service, injectDeps)
	end

	print(currentEnv .. " services started in " .. os.clock() - t0 .. "s")
end


--@annotationInit
function remote(anot)
	local callback = anot.getAdornee()
	local anotType = anot.args[1] --event or function
	local remote = remoteRoot[anot.remote_parent]:WaitForChild(anot.remote_name)

	if anotType == "event" then
		assert(remote:IsA("RemoteEvent"), "Expected RemoteEvent")
		if isServer then
			remote.OnServerEvent:Connect(callback)
		else
			remote.OnClientEvent:Connect(callback)
		end
	else
		assert(remote:IsA("RemoteFunction"), "Expected RemoteFunction")
		if isServer then
			remote.OnServerInvoke = callback
		else
			remote.OnClientInvoke = callback
		end
	end
end


return {
	initServices = initServices,
	bindTag = bindTag,
	remote = remote,
}