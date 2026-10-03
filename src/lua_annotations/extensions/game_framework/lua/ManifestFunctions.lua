-- Implements manifest service dependencies, component lifecycle, and remotes.
-- Generated manifests append these methods to bind annotation metadata to the runtime.

-- Types --

local CollectionService = game:GetService("CollectionService")
local RunService = game:GetService("RunService")

type Cleanup = () -> ()
type CleanupSentinel = {}
type CleanupValue = Cleanup | CleanupSentinel
type RemoteDeps = { [string]: unknown }
type ServiceDeps = {
	[string]: unknown,
	client: RemoteDeps?,
	server: RemoteDeps?,
}
type ComponentState = { [string]: unknown }
type ComponentInstanceMap = { [Instance]: unknown }
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
type DataService = { [Instance]: ComponentState }

local isStudio = RunService:IsStudio()
local NO_CLEANUP: CleanupSentinel = {}

-- Helpers --

local function log(message: string): ()
	if isStudio then
		print("[LuaAnnotations] " .. message)
	end
end

local function getRemoteTargetEnv(manifestApi: { read environment: string }): "client" | "server"
	return if manifestApi.environment == "server" then "client" else "server"
end

-- Annotation modules provide their own fields and initializer signatures; augmentation dispatches those methods dynamically.
-- Constructed values are component state with class lookup, rather than the class module itself.
local function makeComponentClass(class: any, dataGetter: ((Instance) -> ComponentState)?): ()
	class.__index = class

	function class.new(inst: Instance, deps: ServiceDeps): ComponentState
		local state: ComponentState = dataGetter and dataGetter(inst) or {}
		local self = setmetatable(state, class)
		-- Component constructors invoke the lifecycle signature selected by their annotation kind.
		local initialize = class._init :: ((ComponentState, Instance, ServiceDeps) -> ())?
		if initialize then
			initialize(self, inst, deps)
		end

		return self
	end
end

local function useCollectionTag(tag: string, consumer: (Instance) -> Cleanup?): ()
	local cleanups = setmetatable({} :: { [Instance]: CleanupValue }, { __mode = "k" })
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

	log("bound tag " .. tag .. " in " .. (os.clock() - t0) .. "s")
end

local function getMainTagForDependency(manifestApi: ManifestApiState, depName: string): string
	local depData = manifestApi:_getModuleInfo(depName).data :: ServiceManifestData?

	assert(depData, ("[LuaAnnotations] Unknown component dependency %q"):format(depName))
	assert(depData.tags and depData.tags[1], ("[LuaAnnotations] Dependency %q has no tags"):format(depName))
	return depData.tags[1]
end

local function initServiceModule(
	manifestApi: ManifestApiState,
	serviceName: string,
	service: any,
	data: ServiceManifestData,
	baseDeps: ServiceDeps
): ()
	if data.kind == "service" then
		-- Service annotations select the dependency-only initializer contract.
		local initialize = service._init :: ((ServiceDeps) -> ())?
		if initialize then
			initialize(baseDeps)
		end

		return
	end

	if data.kind == "initService" then
		service(baseDeps)
		return
	end

	local tags = assert(data.tags, ("[LuaAnnotations] No tags for component %q"):format(serviceName))
	local mainTag = assert(tags[1], ("[LuaAnnotations] No tags for component %q"):format(serviceName))
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
		instances = setmetatable({}, { __mode = "k" })
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

						assert(createdDepTags, "Component dependencies require a created-tag lookup")
						createdDepTags[dep] = depTag
					end

					depInstances = manifestApi._componentInstances[dep]
					depObj = depInstances and depInstances[inst]

					assert(depObj, ("[LuaAnnotations] Failed to resolve dependency %q for %q"):format(dep, serviceName))
				end

				deps[dep] = depObj
			end

			local obj = service.new(inst, deps)
			instances[inst] = obj

			return function(): ()
				instances[inst] = nil

				-- Component cleanup is an optional method on its constructed state.
				local destroy = obj._destroy :: ((ComponentState) -> ())?
				if destroy then
					destroy(obj)
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
-- An explicit self contract keeps callers from inheriting recursive method inference from the manifest implementation.
function ManifestAPI.getServiceDeps(
	self: ManifestApiState,
	serviceName: string,
	runDependencyInit: boolean?
): ServiceDeps
	if runDependencyInit == nil then
		runDependencyInit = true
	end

	local data = self:_getModuleInfo(serviceName).data :: ServiceManifestData?

	assert(data ~= nil, ("[LuaAnnotations] Module %q has no manifest data"):format(serviceName))

	local injectDeps: ServiceDeps = {}
	local remoteTargetEnv = getRemoteTargetEnv(self)
	local remoteDeps: RemoteDeps = {}
	injectDeps[remoteTargetEnv] = remoteDeps

	for _, dep in ipairs(data.depends.services or {}) do
		if runDependencyInit then
			injectDeps[dep] = self:startService(dep)
		else
			injectDeps[dep] = self:getModule(dep)
		end
	end

	for _, dep in ipairs(data.depends.remotes or {}) do
		remoteDeps[dep] = self:_getHookFun({ module = "Lifecycle", method = "getRemoteTable" })(self, dep)
	end

	return injectDeps
end

--[[
    Starts and returns the requested service, component, initService, or dependency module.
    @param serviceName The manifest module name to initialize or load.
    @param deps An optional dependency table to inject instead of building one with getServiceDeps.
    @return The loaded module or started service object for the requested manifest entry.
]]
function ManifestAPI.startService(self: ManifestApiState, serviceName: string, deps: ServiceDeps?): unknown
	local moduleInfo = self:_getModuleInfo(serviceName)
	local data = moduleInfo.data :: ServiceManifestData?

	if data == nil or data.kind == "dependency" then
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
function ManifestAPI:setRemoteService(name: string, service: {}?)
	self._remoteCache[name] = service
end

ManifestAPI._useCollectionTag = useCollectionTag
