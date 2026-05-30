-- Generated using lua-anot; do not edit manually.
local ManifestAPI = {}
ManifestAPI.__index = ManifestAPI

local function waitForPath(path)
	local cur = path[1]
	for i = 2, #path do
		cur = cur:WaitForChild(path[i])
	end
	return cur
end

function ManifestAPI.new(data)
	return setmetatable({
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
	}, ManifestAPI)
end

function ManifestAPI:_getModuleInfo(moduleName)
	local moduleInfo = self.manifest.modules[moduleName]
	assert(moduleInfo ~= nil, ('[LuaAnnotations] Unknown manifest module %q'):format(moduleName))
	return moduleInfo
end

function ManifestAPI:_getHookFun(hook)
	return self:getCached(hook.module)[hook.method]
end

function ManifestAPI:_runAnnotationHandlers(moduleName, moduleInfo)
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

function ManifestAPI:_runModuleHandlers(moduleName, moduleInfo)
	if self._ranModuleHandlers[moduleName] then
		return
	end

	self._ranModuleHandlers[moduleName] = true

	for _, hook in ipairs(self.manifest.hooks.module_handlers) do
		self:_getHookFun(hook)(self, moduleInfo.data, moduleName)
	end
end

function ManifestAPI:getCached(moduleName)
	local cachedModule = self._cache[moduleName]
	if cachedModule == nil then
		local path = self.modulePaths[moduleName]
		assert(path ~= nil, ('[LuaAnnotations] Unknown cached module %q'):format(moduleName))
		cachedModule = require(waitForPath(path))
		self._cache[moduleName] = cachedModule
	end
	return cachedModule
end

function ManifestAPI:getModule(moduleName)
	return self:getCached(moduleName)
end

function ManifestAPI:loadModule(moduleName)
	local moduleInfo = self:_getModuleInfo(moduleName)
	local module = self:getCached(moduleName)

	self:_runAnnotationHandlers(moduleName, moduleInfo)
	self:_runModuleHandlers(moduleName, moduleInfo)

	return module
end

function ManifestAPI:runPreInitHooks()
	for _, hook in ipairs(self.manifest.hooks.pre_init) do
		self:_getHookFun(hook)(self)
	end
end

function ManifestAPI:loadAllModules()
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

function ManifestAPI:runPostInitHooks()
	for _, hook in ipairs(self.manifest.hooks.post_init) do
		task.spawn(self:_getHookFun(hook), self)
	end
end

--{function_appends}

return ManifestAPI
