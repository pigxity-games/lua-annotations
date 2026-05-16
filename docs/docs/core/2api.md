# API Usage
Extensions are python modules which register annotations and build hooks. The default manifest extension and the game framework extension both use this API internally, so you may see the source code under `src/lua_annotations/extensions` for examples.

Every extension module needs a `load(ctx)` function:

```python title="tools/my_extension.py"
from lua_annotations.api.annotations import AnnotationBuildCtx, AnnotationDef, Extension, ExtensionRegistry


class MyExtension(Extension):
    def on_build_module(self, ctx: AnnotationBuildCtx):
        print(ctx.annotation.get_adornee_name())

    def load(self, ctx: ExtensionRegistry):
        ctx.register_anot(
            AnnotationDef(
                'myModule',
                scope='module',
                on_build=self.on_build_module,
            )
        )


def load(ctx: ExtensionRegistry):
    ctx.register_extension(MyExtension())
```

Then add it to your config:

```json title="annotations.config.json"
{
    "extensions": [
        {"kind": "path", "expr": "tools/my_extension.py"}
    ]
}
```

## Annotation definitions
`AnnotationDef` describes how an annotation is parsed and when it is exported to runtime.

```python
AnnotationDef(
    name='example',
    args=[str],
    kwargs={'depends': default_list},
    retention='build',
    scope='module',
    on_build=callback,
)
```

Important fields:

* `name`: the annotation name used after `--@`.
* `args`: positional argument processors. For example, `str`, `default_list`, or a custom function.
* `kwargs`: keyword argument processors.
* `scope`: what the annotation may be attached to: `module`, `method`, `type`, or `returned_value`.
* `retention`: `build`, `init`, or `runtime`. Non-build annotations are written into the generated init manifest.
* `on_build`: a callback called after the annotation is parsed.

The helper functions in `lua_annotations.api.arguments` are useful for common argument shapes:

* `list_arg`: parses `[A, B, C]`.
* `default_list`: parses `[A, B]`, or wraps a single value as `[A]`.
* `literal_builder`: creates an argument parser limited to a set of strings.

## Extension hooks
An `Extension` may implement these methods:

```python
from lua_annotations.api.annotations import Extension, ExtensionRegistry, FileBuildCtx
from lua_annotations.build_process import PostProcessCtx


class MyExtension(Extension):
    def load(self, ctx: ExtensionRegistry):
        ...

    def on_file_process(self, ctx: FileBuildCtx):
        ...

    def on_post_process(self, ctx: PostProcessCtx):
        ...
```

`load` is where annotations and dependent extensions are registered.

`on_file_process` runs after a lua file with annotations has been parsed.

`on_post_process` runs after all environments in a workspace have been processed. Use this for generated files that need global information.

## Registering extensions
Inside a module-level `load(ctx)` function, register an instance of your extension:

```python
def load(ctx: ExtensionRegistry):
    ctx.register_extension(MyExtension())
```

You can also declare dependencies and hook ordering:

```python
ctx.register_extension(MyExtension(), deps=['ManifestExtension'], hook_order='before')
```

`deps` affects extension load order. `hook_order='before'` moves the extension's file and post-process hooks earlier, which is useful when one extension needs to add data before another one writes output.

## Parser notes
Annotations are lua comments which should be placed immediately before the thing they annotate:

```lua
--@module
local module = {}

--@myMethod, hello, depends=[A, B]
function module.run()
end

return module
```

The parser understands modules returned directly, modules returned through table entries, inline method definitions, literal return tables, and Luau type declarations.

If you want to annotate many files with the same rule, add an `annotation-meta.json` file to a directory:

```json title="annotation-meta.json"
{
    "regex_annotate": {
        "^local \\w+ = \\{\\}": "module"
    }
}
```

The regex rules apply to direct lua files in that directory.

The annotation value may be written with or without the `--@` prefix. Both `"module"` and `"@module"` are normalized before parsing.
