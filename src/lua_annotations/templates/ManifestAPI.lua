-- Generated using lua-anot; do not edit manually.

-- /// Core Manifest API ///

-- Types

type ModulePath = { [number]: Instance | string }
type ModulePathExport = {
	path: ModulePath,
	export: string?,
}
type ModulePathEntry = ModulePath | ModulePathExport
type ManifestAnnotation = {
	name: string,
	data: any,
	args: { any }?,
	kwargs: { [string]: any }?,
}
type ManifestHook = {
	module: string,
	method: string,
}
type ManifestModuleInfo = {
	annotations: { [string]: { ManifestAnnotation } },
	data: any,
}
type ManifestHooks = {
	pre_init: { ManifestHook },
	module_handlers: { ManifestHook },
	post_init: { ManifestHook },
	annotation_handlers: { [string]: ManifestHook },
}
type ManifestData = {
	modules: { [string]: ManifestModuleInfo },
	hooks: ManifestHooks,
	load_order: { string },
	remotes: any,
}
type ManifestInitData = {
	environment: string,
	modulePaths: { [string]: ModulePathEntry },
	manifest: ManifestData,
}
type ManifestApiFields = {
	environment: string,
	modulePaths: { [string]: ModulePathEntry },
	manifest: ManifestData,
	_cache: { [string]: any },
	_loadedAnnotations: { [string]: boolean },
	_ranModuleHandlers: { [string]: boolean },
	_remoteCache: { [string]: any },
	_componentInstances: { [string]: { [Instance]: any } },
	_startedServices: { [string]: any },
	_startingServices: { [string]: boolean },
}

local ManifestAPI = {}
ManifestAPI.__index = ManifestAPI

type ManifestApiState = typeof(setmetatable({} :: ManifestApiFields, ManifestAPI))

-- Helpers --

local function waitForPath(path: ModulePath): Instance
	local cur = path[1] :: Instance
	for i = 2, #path do
		cur = cur:WaitForChild(path[i] :: string)
	end
	return cur
end


local function applyExport(value: any, exportName: string?): any
	if not exportName then
		return value
	end

	return value[exportName]
end

-- Methods --

--[[
    Creates a manifest API object backed by generated manifest data and runtime caches.
    @param data A table containing the generated environment name, module path map, and manifest payload.
    @return A new ManifestAPI instance for the generated manifest.
]]
function ManifestAPI.new(data: ManifestInitData): ManifestApiState
	local state: ManifestApiFields = {
		environment = data.environment,
		modulePaths = data.modulePaths,
		manifest = data.manifest,
		_cache = {},
		_loadedAnnotations = {},
		_ranModuleHandlers = {},
		_remoteCache = {},
		_componentInstances = {},
		_startedServices = {},
		_startingServices = {},
	}

	return setmetatable(state, ManifestAPI)
end


--[[
    Looks up manifest metadata for a generated module and errors when it is missing.
    @param moduleName The manifest module name to resolve.
    @return The manifest module info table for the requested module.
]]
function ManifestAPI:_getModuleInfo(moduleName: string): ManifestModuleInfo
	local moduleInfo = self.manifest.modules[moduleName]
	assert(moduleInfo ~= nil, ('[LuaAnnotations] Unknown manifest module %q'):format(moduleName))
	return moduleInfo
end


--[[
    Loads the runtime function referenced by a generated manifest hook entry.
    @param hook A manifest hook table containing the module and method names to resolve.
    @return The callable hook function from the cached module export.
]]
function ManifestAPI:_getHookFun(hook: ManifestHook): (...any) -> ...any
	return self:getModule(hook.module)[hook.method] :: (...any) -> ...any
end


--[[
    Runs retained annotation handlers for a module exactly once.
    @param moduleName The manifest module name whose retained annotations should be processed.
    @param moduleInfo The manifest module info table containing annotation data for the module.
]]
function ManifestAPI:_runAnnotationHandlers(moduleName: string, moduleInfo: ManifestModuleInfo): ()
	if self._loadedAnnotations[moduleName] then
		return
	end

	self._loadedAnnotations[moduleName] = true

	for methodName, annotations in pairs(moduleInfo.annotations) do
		for _, anot in ipairs(annotations) do
			local hook = self.manifest.hooks.annotation_handlers[anot.name]
			if hook ~= nil then
				self:_getHookFun(hook)(self, anot, methodName, moduleInfo.data, moduleName)
			end
		end
	end
end


--[[
    Runs registered module handlers for a module exactly once.
    @param moduleName The manifest module name whose module handlers should be processed.
    @param moduleInfo The manifest module info table passed into each module handler.
]]
function ManifestAPI:_runModuleHandlers(moduleName: string, moduleInfo: ManifestModuleInfo): ()
	if self._ranModuleHandlers[moduleName] then
		return
	end

	self._ranModuleHandlers[moduleName] = true

	for _, hook in ipairs(self.manifest.hooks.module_handlers) do
		self:_getHookFun(hook)(self, moduleInfo.data, moduleName)
	end
end


--[[
    Returns a generated module without running annotation or module handlers, caching it for future calls.
    @param moduleName The manifest module name to require from the generated module path map.
    @return The cached module value or requested export for the module.
]]
function ManifestAPI:getModule(moduleName: string): any
	local cachedModule = self._cache[moduleName]
	if cachedModule == nil then
		local moduleData: any = self.modulePaths[moduleName]
		assert(moduleData ~= nil, ('[LuaAnnotations] Unknown cached module %q'):format(moduleName))

		local path = moduleData.path or moduleData
		local exportName = moduleData.export
		cachedModule = applyExport(require(waitForPath(path)), exportName)
		self._cache[moduleName] = cachedModule
	end
	return cachedModule
end


--[[
    Loads a generated module and runs its retained annotation and module handlers.
    @param moduleName The manifest module name to load from the generated manifest.
    @return The loaded module value or requested export for the module.
]]
function ManifestAPI:loadModule(moduleName: string): any
	local moduleInfo = self:_getModuleInfo(moduleName)
	local module = self:getModule(moduleName)

	self:_runAnnotationHandlers(moduleName, moduleInfo)
	self:_runModuleHandlers(moduleName, moduleInfo)

	return module
end


--[[
    Runs all generated pre-init hooks in manifest order.
]]
function ManifestAPI:runPreInitHooks(): ()
	for _, hook in ipairs(self.manifest.hooks.pre_init) do
		self:_getHookFun(hook)(self)
	end
end


--[[
    Loads every generated manifest module, honoring explicit load order before remaining modules.
]]
function ManifestAPI:loadAllModules(): ()
	local modules = self.manifest.modules
	local loadOrder = self.manifest.load_order

	for _, moduleName in ipairs(loadOrder) do
		if modules[moduleName] ~= nil then
			self:loadModule(moduleName)
		end
	end

	for moduleName in pairs(modules) do
		if not self._ranModuleHandlers[moduleName] then
			self:loadModule(moduleName)
		end
	end
end


--[[
    Schedules all generated post-init hooks to run asynchronously.
]]
function ManifestAPI:runPostInitHooks(): ()
	for _, hook in ipairs(self.manifest.hooks.post_init) do
		task.spawn(self:_getHookFun(hook), self)
	end
end


--{function_appends}

return ManifestAPI
