local CollectionService = game:GetService('CollectionService')
local RunService = game:GetService('RunService')

local isStudio = RunService:IsStudio()
local NO_CLEANUP = {}


local function log(message)
	if isStudio then
		print('[LuaAnnotations] ' .. message)
	end
end


local function getRemoteTargetEnv(manifestApi)
	return if manifestApi.environment == 'server' then 'client' else 'server'
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
	local cleanups = setmetatable({}, { __mode = 'k' })
	local t0 = os.clock()

	local function onAdd(inst)
		if cleanups[inst] ~= nil then
			return
		end

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

	log('bound tag ' .. tag .. ' in ' .. (os.clock() - t0) .. 's')
end


local function getMainTagForDependency(manifestApi, depName)
	local depData = manifestApi:_getModuleInfo(depName).data
	assert(depData, ('[LuaAnnotations] Unknown component dependency %q'):format(depName))
	assert(depData.tags and depData.tags[1], ('[LuaAnnotations] Dependency %q has no tags'):format(depName))
	return depData.tags[1]
end


local function initServiceModule(manifestApi, serviceName, service, data, baseDeps)
	if data.kind == 'service' then
		if service._init then
			service._init(baseDeps)
		end
		return
	end

	if data.kind == 'initService' then
		service(baseDeps)
		return
	end

	local mainTag = assert(data.tags[1], ('[LuaAnnotations] No tags for component %q'):format(serviceName))
	local getComponentData
	local dataService

	if data.data_service then
		dataService = manifestApi:getModule(data.data_service)
		getComponentData = function(inst)
			local state = dataService[inst]
			if not state then
				state = {}
				dataService[inst] = state
			end
			return state
		end

		for inst in pairs(dataService) do
			inst:AddTag(mainTag)
		end
	end

	makeComponentClass(service, getComponentData)

	local instances = manifestApi._componentInstances[serviceName]
	if not instances then
		instances = setmetatable({}, { __mode = 'k' })
		manifestApi._componentInstances[serviceName] = instances
	end

	for _, tag in ipairs(data.tags) do
		local componentDeps = data.depends.components
		local hasComponentDeps = #componentDeps > 0

		useCollectionTag(tag, function(inst)
			local deps = hasComponentDeps and table.clone(baseDeps) or baseDeps
			local createdDepTags = hasComponentDeps and {} or nil

			for _, dep in ipairs(componentDeps) do
				local depInstances = manifestApi._componentInstances[dep]
				local depObj = depInstances and depInstances[inst]

				if not depObj then
					local depTag = getMainTagForDependency(manifestApi, dep)

					if not inst:HasTag(depTag) then
						inst:AddTag(depTag)
						assert(createdDepTags)
						createdDepTags[dep] = depTag
					end

					depInstances = manifestApi._componentInstances[dep]
					depObj = depInstances and depInstances[inst]
					assert(depObj, ('[LuaAnnotations] Failed to resolve dependency %q for %q'):format(dep, serviceName))
				end

				deps[dep] = depObj
			end

			local obj = service.new(inst, deps)
			instances[inst] = obj

			return function()
				instances[inst] = nil

				if obj._destroy then
					obj:_destroy()
				end

				if createdDepTags then
					for _, depTag in pairs(createdDepTags) do
						if inst:HasTag(depTag) then
							inst:RemoveTag(depTag)
						end
					end
				end

				if dataService then
					dataService[inst] = nil
				end
			end
		end)
	end
end


function ManifestAPI:getServiceDeps(serviceName, runDependencyInit)
	if runDependencyInit == nil then
		runDependencyInit = true
	end

	local data = self:_getModuleInfo(serviceName).data
	assert(data ~= nil, ('[LuaAnnotations] Module %q has no manifest data'):format(serviceName))

	local injectDeps = {}
	local remoteTargetEnv = getRemoteTargetEnv(self)
	injectDeps[remoteTargetEnv] = {}

	for _, dep in ipairs(data.depends.services or {}) do
		if runDependencyInit then
			injectDeps[dep] = self:startService(dep)
		else
			injectDeps[dep] = self:getModule(dep)
		end
	end

	for _, dep in ipairs(data.depends.remotes or {}) do
		injectDeps[remoteTargetEnv][dep] = self:getCached('Lifecycle').getRemoteTable(self, dep)
	end

	return injectDeps
end


function ManifestAPI:startService(serviceName, deps)
	local moduleInfo = self:_getModuleInfo(serviceName)
	local data = moduleInfo.data

	if data == nil or data.kind == 'dependency' then
		return self:loadModule(serviceName)
	end

	self:_runAnnotationHandlers(serviceName, moduleInfo)

	local service = self:getModule(serviceName)
	if self._startedServices[serviceName] then
		return service
	end

	if self._startingServices[serviceName] then
		return service
	end

	self._startingServices[serviceName] = true
	initServiceModule(self, serviceName, service, data, deps or self:getServiceDeps(serviceName))
	self._startingServices[serviceName] = nil
	self._startedServices[serviceName] = service

	return service
end


ManifestAPI._useCollectionTag = useCollectionTag
