local remoteInfoByEnv = nil

function m.getServiceData(serviceName)
	local data = m.getModuleData(serviceName)
	assert(data, ("[LuaAnnotations] Unknown service %q"):format(serviceName))
	return data
end

function m.getService(serviceName)
	return m.getCached(serviceName)
end

function m.getServiceDependencies(serviceName)
	return m.getServiceData(serviceName).depends
end

function m.getRemoteInfoByEnv()
	if remoteInfoByEnv then
		return remoteInfoByEnv
	end

	remoteInfoByEnv = {
		client = {},
		server = {},
	}

	for moduleName, moduleData in pairs(m.manifest.modules) do
		for env, remotes in pairs(moduleData.data.remotes or {}) do
			local serviceInfo = remoteInfoByEnv[env]
			if serviceInfo then
				serviceInfo[moduleName] = remotes
			end
		end
	end

	return remoteInfoByEnv
end

function m.buildServiceDependencies(serviceName, options)
	local Lifecycle = m.getCached("Lifecycle")
	return Lifecycle.buildServiceDeps(m, m.getServiceData(serviceName), options)
end

function m.initService(serviceName, options)
	local Lifecycle = m.getCached("Lifecycle")
	return Lifecycle.initService(m, m.getServiceData(serviceName), serviceName, options)
end

function m.callRemote(serviceName, methodName, options, ...)
	local Lifecycle = m.getCached("Lifecycle")
	return Lifecycle.callRemote(m, serviceName, methodName, options, ...)
end
