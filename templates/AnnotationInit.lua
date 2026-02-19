-- Generated using lua-anot; do not edit manually.

--manifest

for _, anot in ipairs(manifest.annotations) do
    local fun = manifest.anot_hooks[anot.name]
    if fun then
        fun(anot, manifest)
    end
end

for _, hook in ipairs(manifest.init_hooks) do
    hook(manifest)
end