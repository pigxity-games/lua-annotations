local ServerScriptService = game:GetService('ServerScriptService')

local ServerManifest = require(ServerScriptService.Generated.Manifest)
local Helpers = require('./helpers')

local module = {}

local function loadServerModules()
	Helpers.loadServerModules(ServerManifest)
end

local function getCounter(inst: Instance)
	local instances = ServerManifest._componentInstances.Counter
	return instances and instances[inst]
end

local function getCounterLogger(inst: Instance)
	local instances = ServerManifest._componentInstances.CounterLogger
	return instances and instances[inst]
end

function module.tagsPresentBeforeLoadCreateComponentsAndRegistryAppliesDefaultData()
	local part1, part2 = Helpers.setupCounterRegistryParts()
	local simplePart = Helpers.createPart('SimpleOriginal')
	simplePart:AddTag('SimpleComponent')

	loadServerModules()

	local counter1 = getCounter(part1)
	local counter2 = getCounter(part2)
	local counterModule = ServerManifest:getModule('Counter')
	local counterRegistry = ServerManifest:getModule('CounterRegistry')

	assert(counter1 ~= nil, 'tagged instances should create counter components when modules load')
	assert(counter2 ~= nil, 'registry entries should create counter components when modules load')
	assert(part2:HasTag('Counter'), 'registry-backed instances should gain the counter tag automatically')
	assert(counterModule.increment ~= nil, 'file exports should resolve to the named Counter module')
	assert(counterRegistry[part1].val == 123, 'file exports should resolve to the named CounterRegistry dependency')
	assert(counter1.instance == part1)
	assert(counter2.instance == part2)
	assert(counter1.count == 0)
	assert(counter1.val == 123)
	assert(counter2.val == nil)
	assert(counter1.isLogging == false)
	assert(simplePart.Name == 'Component', 'pre-tagged simple components should run as soon as they are loaded')

	counter1:increment(nil, nil)
	assert(counter1.count == 1)
	assert(part1.Name == '1', 'counter methods should run against the bound instance')
end

function module.simpleComponentCleanupRevertsThePartNameWhenTheTagIsRemoved()
	Helpers.setupCounterRegistryParts()

	local simplePart = Helpers.createPart('SimpleOriginal')
	simplePart:AddTag('SimpleComponent')

	loadServerModules()
	assert(simplePart.Name == 'Component')

	simplePart:RemoveTag('SimpleComponent')
	assert(simplePart.Name == 'SimpleOriginal', 'removing the simple component tag should run its cleanup function')
end

function module.counterRegistryCanCreateANewComponentFromDocumentationStyleData()
	Helpers.setupCounterRegistryParts()
	loadServerModules()

	local registry = ServerManifest:getModule('CounterRegistry')
	local part3 = Helpers.createPart('Part3')
	registry[part3] = {
		val = 456,
	}

	part3:AddTag('Counter')

	local counter3 = getCounter(part3)
	assert(counter3 ~= nil, 'adding the counter tag after writing registry data should create a component')
	assert(counter3.val == 456)
	assert(counter3.count == 0)
	assert(counter3.instance == part3)
end

function module.counterLoggerTogglesLoggingAndAutoCreatesMissingCounterDependencies()
	Helpers.setupCounterRegistryParts()

	local existingCounterPart = Helpers.createPart('ExistingCounter')
	existingCounterPart:AddTag('Counter')

	local loggerOnlyPart = Helpers.createPart('LoggerOnly')
	loggerOnlyPart:AddTag('CounterLogger')

	loadServerModules()

	local existingCounter = getCounter(existingCounterPart)
	assert(existingCounter ~= nil)
	assert(existingCounter.isLogging == false)

	existingCounterPart:AddTag('CounterLogger')

	local existingLogger = getCounterLogger(existingCounterPart)
	assert(existingLogger ~= nil, 'adding CounterLogger to an existing counter should create the logger component')
	assert(existingCounter.isLogging == true, 'adding CounterLogger should toggle the counter logging flag on')

	existingCounterPart:RemoveTag('CounterLogger')
	assert(getCounterLogger(existingCounterPart) == nil)
	assert(existingCounter.isLogging == false, 'removing CounterLogger should reset the counter logging flag')
	assert(existingCounterPart:HasTag('Counter'), 'removing CounterLogger should not remove a pre-existing Counter tag')

	local autoCreatedCounter = getCounter(loggerOnlyPart)
	local autoCreatedLogger = getCounterLogger(loggerOnlyPart)

	assert(autoCreatedCounter ~= nil, 'CounterLogger should create Counter automatically when needed')
	assert(autoCreatedLogger ~= nil)
	assert(loggerOnlyPart:HasTag('Counter'), 'logger dependencies should add the missing Counter tag')
	assert(autoCreatedCounter.isLogging == true)

	loggerOnlyPart:RemoveTag('CounterLogger')
	assert(getCounterLogger(loggerOnlyPart) == nil)
	assert(autoCreatedCounter.isLogging == false, 'logger cleanup should set isLogging back to false')
	assert(not loggerOnlyPart:HasTag('Counter'), 'auto-created Counter tags should be removed when the logger is removed')
	assert(getCounter(loggerOnlyPart) == nil, 'removing the auto-created Counter tag should clean up the Counter component')
end

return module

