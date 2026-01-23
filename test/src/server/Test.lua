type x = 'test' | 'hello'

type y = {
    x: any,
    y: string,
    z: x
}

--@service
local module = {
    --@test
    testfun3 = function()
        
    end
}

--@test
function module.testfun1()
    
end

--@test
module.testfun2 = function()
    
end

--@test
function module:testfun4()

end