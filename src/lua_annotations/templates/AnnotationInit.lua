-- Generated using lua-anot; do not edit manually.

local t0 = os.clock()

--manifest

--lifecycle
for _, fun in ipairs(manifest.init_hooks) do
    fun(manifest)
end

for _, anot in ipairs(manifest.annotations) do
    local fun = manifest.anot_hooks[anot.name]
    if fun then
        fun(anot, manifest)
    end
end

for _, fun in ipairs(manifest.post_init_hooks) do
    fun(manifest)
end

print("Started (env) services in " .. (os.clock() - t0) .. "s")