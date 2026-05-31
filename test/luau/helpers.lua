local ReplicatedStorage = game:GetService('ReplicatedStorage')

local module = {}

function module.setupRemotes()
	getEnvironment():loadRojoModel("./fixtures/src/shared/Generated/Remotes.model.json")
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
