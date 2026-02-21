-- Generated using lua-anot; do not edit manually.

--manifest


--lifecycle
for _, anot in ipairs(manifest.annotations) do
    local fun = manifest.anot_hooks[anot.name]
    if fun then
        fun(anot, manifest)
    end
end

for _, fun in ipairs(manifest.init_hooks) do
    fun(manifest)
end