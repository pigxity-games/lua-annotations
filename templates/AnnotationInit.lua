-- Generated using lua-anot; do not edit manually.

--manifest

--helpers
local function walkExports(module, exports)
    local cur = module
    for _, exp in ipairs(exports) do
        cur = cur[exp]
    end
    return cur
end


--llifecycle
for _, anot in ipairs(manifest.annotations) do
    local path = manifest.anot_hooks[anot.name]
    if path then
        local fun = walkExports(path.module, path.exports)

        local mod = require(anot.module)
        if anot.exports then
            mod = walkExports(mod, anot.exports)
        end

        fun(anot, mod, manifest)
    end
end

for _, path in ipairs(manifest.init_hooks) do
    local fun = walkExports(path.module, path.exports)
    fun(manifest)
end