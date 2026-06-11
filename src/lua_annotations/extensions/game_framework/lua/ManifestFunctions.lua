-- /// Game-Framework Manifest API ///

-- Types --

local CollectionService = game:GetService('CollectionService')
local RunService = game:GetService('RunService')

type Cleanup = () -> ()
type CleanupSentinel = {}
type CleanupValue = Cleanup | CleanupSentinel
type RemoteDeps = { [string]: any }
type ServiceDeps = {
	[string]: any,
	client: RemoteDeps?,
	server: RemoteDeps?,
}
type ComponentState = { [string]: any }
type ComponentInstanceMap = { [Instance]: any }
type ComponentInstanceRegistry = { [string]: ComponentInstanceMap }
type ServiceManifestData = {
	kind: string,
	tags: { string }?,
	data_service: string?,
	depends: {
		services: { string }?,
		remotes: { string }?,
		components: { string }?,
	},
}
type ServiceManifestModuleInfo = {
	data: ServiceManifestData,
	annotations: { [string]: { any } }?,
}
type ServiceManifestApi = {
	environment: string,
	_componentInstances: ComponentInstanceRegistry,
	_startedServices: { [string]: any },
	_startingServices: { [string]: boolean },
	_getModuleInfo: (self: any, moduleName: string) -> ServiceManifestModuleInfo,
	getModule: (self: any, moduleName: string) -> any,
	getCached: (self: any, moduleName: string) -> any,
	startService: (self: any, serviceName: string, deps: ServiceDeps?) -> any,
}
type DataService = { [Instance]: ComponentState }


local isStudio = RunService:IsStudio()
local NO_CLEANUP: CleanupSentinel = {}

-- Helpers --

local function log(message: string): ()
	if isStudio then
		print('[LuaAnnotations] ' .. message)
	end
end


local function getRemoteTargetEnv(manifestApi: ServiceManifestApi): 'client' | 'server'
	return if manifestApi.environment == 'server' then 'client' else 'server'
end


local function makeComponentClass<T>(class: T, dataGetter: ((Instance) -> ComponentState)?): ()
	local classTable = class :: any
	classTable.__index = class

	function classTable.new(inst: Instance, deps: ServiceDeps): T
		local self = setmetatable(dataGetter and dataGetter(inst) or {}, classTable)
		if classTable._init then
			classTable._init(self, inst, deps)
		end
		return self
	end
end


local function useCollectionTag(tag: string, consumer: (Instance) -> Cleanup?): ()
	local cleanups = setmetatable({} :: { [Instance]: CleanupValue }, { __mode = 'k' })
	local t0 = os.clock()

	local function onAdd(inst: Instance): ()
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

	local function onRemove(inst: Instance): ()
		local cleanup = cleanups[inst]
		if cleanup then
			if cleanup ~= NO_CLEANUP then
				(cleanup :: Cleanup)()
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


local function getMainTagForDependency(manifestApi: ServiceManifestApi, depName: string): string
	local depData = manifestApi:_getModuleInfo(depName).data
	assert(depData, ('[LuaAnnotations] Unknown component dependency %q'):format(depName))
	assert(depData.tags and depData.tags[1], ('[LuaAnnotations] Dependency %q has no tags'):format(depName))
	return depData.tags[1]
end


local function initServiceModule(
	manifestApi: ServiceManifestApi,
	serviceName: string,
	service: any,
	data: ServiceManifestData,
	baseDeps: ServiceDeps
): ()
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

	local tags = assert(data.tags, ('[LuaAnnotations] No tags for component %q'):format(serviceName))
	local mainTag = assert(tags[1], ('[LuaAnnotations] No tags for component %q'):format(serviceName))
	local getComponentData: ((Instance) -> ComponentState)?
	local dataService: DataService?

	if data.data_service then
		local resolvedDataService = manifestApi:getModule(data.data_service) :: DataService
		dataService = resolvedDataService
		getComponentData = function(inst: Instance): ComponentState
			local state = resolvedDataService[inst]
			if not state then
				state = {}
				resolvedDataService[inst] = state
			end
			return state
		end

		for inst in pairs(resolvedDataService) do
			inst:AddTag(mainTag)
		end
	end

	makeComponentClass(service, getComponentData)

	local instances = manifestApi._componentInstances[serviceName]
	if not instances then
		instances = setmetatable({}, { __mode = 'k' })
		manifestApi._componentInstances[serviceName] = instances
	end

	for _, tag in ipairs(tags) do
		local componentDeps = data.depends.components :: { string }
		local hasComponentDeps = #componentDeps > 0

		useCollectionTag(tag, function(inst: Instance): Cleanup
			local deps = (hasComponentDeps and table.clone(baseDeps) or baseDeps) :: ServiceDeps
			local createdDepTags = (hasComponentDeps and {} or nil) :: { [string]: string }?

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

			return function(): ()
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

-- Methods --

--[[
    Builds and returns the dependency table for the requested service or component.
    @param serviceName The manifest module name whose dependencies should be resolved.
    @param runDependencyInit When true or nil, dependent services are started before being injected. When false, dependencies are required without running their startup logic.
    @return A deps table containing resolved service dependencies and cross-environment remote wrappers keyed by their manifest names.
]]
function ManifestAPI:getServiceDeps(serviceName: string, runDependencyInit: boolean?): ServiceDeps
	if runDependencyInit == nil then
		runDependencyInit = true
	end

	local data = self:_getModuleInfo(serviceName).data
	assert(data ~= nil, ('[LuaAnnotations] Module %q has no manifest data'):format(serviceName))

	local injectDeps: any = {}
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
		injectDeps[remoteTargetEnv][dep] = self:getModule('Lifecycle').getRemoteTable(self, dep)
	end

	return injectDeps :: ServiceDeps
end


--[[
    Starts and returns the requested service, component, initService, or dependency module.
    @param serviceName The manifest module name to initialize or load.
    @param deps An optional dependency table to inject instead of building one with getServiceDeps.
    @return The loaded module or started service object for the requested manifest entry.
]]
function ManifestAPI:startService(serviceName: string, deps: ServiceDeps?): any
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


--[[
	Sets a service inside of the remoteCache, allowing for creating fake remote services in tests.
	@param name The name of the remote service.
	@param service The service table to set; `nil` clears the cached entry.
]]
function ManifestAPI:setRemoteService(name: string, service: {[any]: any})
	self._remoteCache[name] = service
end


ManifestAPI._useCollectionTag = useCollectionTag
