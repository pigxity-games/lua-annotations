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

--@moduleTest
local module2 = {

}

--@methodTest
function module2.testfun()

end

--@methodTest, hello, testKwarg=world
function module.testfun1(t: any, t2: string): number
    
end

--@methodTest, testKwarg=world
module.testfun2 = function()
    
end

--@methodTest, hello
function module:testfun4(): string

end

return {
    TestModule = module,
    TestModule2 = module2
}