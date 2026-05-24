local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")

local m = {}

m.paths = {
    Lifecycle = {ReplicatedStorage, "Gemerated", "_Internal", "Lifecycle"},
    SomeModule = {ReplicatedStorage, "SomeModule"},
    MyService = {ServerScriptService, "MyService"},
    MyService2 = {ServerScriptService, "MyService2"},
}

m.manifest = {
    hooks = {
        pre_init = {},
        annotation_handlers = {
            remote = {
                module = "Lifecycle",
                method = "remote"
            },
        },
        module_handlers = {
            {
                module = "Lifecycle",
                method = "initService"
            }  
        },
        post_init = {
            {
                module = "SomeModule",
                method = "somePostInitHook"
            }
        }
    },
    modules = {
        MyService = {
            annotations = {
                printMessage = {
                    name = "remote",
                    args = {
                        "function"
                    },
                    kwargs = {},
                    data = {}
                }
            },
            data = {
                kind = "service",
                depends = {
                    services = {"MyService2"},
                    remotes = {}
                }
            }
        },
        MyService2 = {
            annotations = {
                _module = {
                    name = "someModuleAnnotationWithCustomData",
                    args = {},
                    kwargs = {},
                    data = {
                        keyInjectedByPython = "valueInjectedByPython"
                    }
                }
            },
            data = {
                kind = "service",
                depends = {
                    services = {},
                    remotes = {"ClientDataController"}
                }
            }
        }
    },
    load_order = {"MyService2", "MyService"}
}

--methods

local cache = {}

local function waitForPath(path)
    local cur = path[1]
    for i = 2, #path do
        cur = cur:WaitForChild(path[i])
    end
    return cur
end

function m.getCached(moduleName)
    local m = cache[moduleName]
    if not m then
        m = require(waitForPath(m.paths[moduleName]))
        cache[moduleName] = m
    end
    return m
end
    
return m