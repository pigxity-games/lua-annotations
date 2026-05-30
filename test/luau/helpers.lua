local ReplicatedStorage = game:GetService('ReplicatedStorage')

local module = {}

function module.ensureChild(parent: Instance, className: string, childName: string)
	local child = parent:FindFirstChild(childName)
	if child then
		return child
	end

	child = Instance.new(className, parent)
	child.Name = childName
	return child
end

function module.setupRemotes()
	local generated = module.ensureChild(ReplicatedStorage, 'Folder', 'Generated')
	local remotes = module.ensureChild(generated, 'Folder', 'Remotes')
	local serviceA = module.ensureChild(remotes, 'Folder', 'ServiceA')
	module.ensureChild(serviceA, 'RemoteFunction', 'pingRemote')
end

function module.createPart(name: string)
	local part = Instance.new('Part')
	part.Name = name
	part.Parent = workspace
	return part
end

function module.setupCounterRegistryParts()
	local part1 = module.createPart('Part1')
	part1:AddTag('Counter')

	local part2 = module.createPart('Part2')

	return part1, part2
end

function module.loadServerModules(serverManifest)
	module.setupRemotes()
	serverManifest:loadAllModules()
end

return module
