type x = 'test' | 'hello'

type y = {
    x: any,
    y: string,
    z: x
}

--@moduleTest
local module = {
    --@test
    testfun3 = function()
        
    end
}

--@methodTest
function module.testfun1(t: any, t2: string)
    
end

--@methodTest
module.testfun2 = function()
    
end

--@methodTest
function module:testfun4()

end

return module