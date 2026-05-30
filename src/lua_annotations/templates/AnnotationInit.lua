-- Generated using lua-anot; do not edit manually.
local t0 = os.clock()
local RunService = game and game:GetService('RunService')
local isStudio = RunService and RunService:IsStudio()

local Manifest = require((env-root)
    :WaitForChild('Generated')
    :WaitForChild('Manifest'))

local initT0 = os.clock()
Manifest:runPreInitHooks()
local preInitTime = os.clock() - initT0

local annotationT0 = os.clock()
Manifest:loadAllModules()
local moduleTime = os.clock() - annotationT0

local postInitT0 = os.clock()
Manifest:runPostInitHooks()
local postInitTime = os.clock() - postInitT0

if isStudio then
    print('[LuaAnnotations] (env) annotations loaded in ' .. (os.clock() - t0) .. 's (pre_init=' .. preInitTime .. 's, modules=' .. moduleTime .. 's, post_init=' .. postInitTime .. 's)')
end
