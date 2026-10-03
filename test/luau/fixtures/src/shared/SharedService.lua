--!strict
-- Exercises shared service loading and arithmetic so generated method contracts can be validated.
--@service
local m = {
	initialized = false,
}

function m._init()
	m.initialized = true
end

function m.add(a: number, b: number): number
	return a + b
end

return m
