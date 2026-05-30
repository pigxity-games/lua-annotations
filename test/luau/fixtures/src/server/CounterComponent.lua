--@component, Counter, data=CounterRegistry
local counter = {
    count = 0
}

function counter:_init(inst: BasePart)
    self.instance = inst
    self.isLogging = false
end

function counter:increment(player: Player, label: TextLabel)
    self.count += 1
    self.instance.Name = tostring(self.count)
end

function counter:_destroy()
    if self.conn then
        self.conn:Disconnect()
    end
end


--@component, CounterLogger, depends=[Counter]
local logger = {
    active = true
}

function logger:_init(inst: BasePart, deps)
    self.inst = inst
    self.Counter = deps.Counter
    self.active = true

    self.Counter.isLogging = true
end

function logger:_destroy()
    self.Counter.isLogging = false
end


--@dependency, load_after=[Counter], typegen=registry
local registry = {}

local part1 = workspace:FindFirstChild('Part1')
if part1 then
    registry[part1] = {
        val = 123
    }
end

local part2 = workspace:FindFirstChild('Part2')
if part2 then
    registry[part2] = {}
end

return {
    Counter = counter,
    CounterLogger = logger,
    CounterRegistry = registry
}

