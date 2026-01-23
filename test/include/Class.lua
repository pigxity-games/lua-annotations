--returns a table type with a .new constructor
type function createConstructor(T: type)
    assert(T:is('table'))

    local initKey = types.singleton('_init')
    local initType = T:readproperty(initKey)
    local newFn

    if initType then
        assert(initType:is('function'))
        local params = initType:parameters()

        local newHead = {}
        for i, type in params.head do
            if i == 1 then continue end
            table.insert(newHead, type)
        end

        newFn = types.newfunction({ head = newHead, }, { head = { T } })
    else
        newFn = types.newfunction({head = {}}, { head = { T }})
    end

    local out = types.newtable()
    out:setproperty(types.singleton('new'), newFn)
    return out
end

--extracts the self parameter from _init()
type function getFields(T: type)
    assert(T:is('table'))

    local initFun = T:readproperty(types.singleton('_init'))
    assert(initFun and initFun:is('function'), 'init is not a functrion')
    
    local params = initFun:parameters()
    return params.head[1]
end

local function class<T>(class: T)
    class.__index = class 

    function class.new(...)
        local self = setmetatable({}, class)
        if class._init then
            class._init(self, ...)
        end
        return self
    end

    return class :: T & createConstructor<T> & getFields<T>
end

return class