# Runtime Annotations
Some annotations only matter while the project is being built, while others need to affect the code at runtime. The core extension generates an init file, a manifest table, and a hook system.

The game framework's `Lifecycle.lua` is the best example of this. It defines runtime behavior for annotations like `@bindTag` and `@remote`, and it starts services after other runtime annotations, using `@onPostInit`.

## Generated init files
The core extension creates these files:

* `Generated/AnnotationInit.server.lua`
* `Generated/AnnotationInit.client.lua`

Each file contains a generated lua `manifest` table containing runtime hooks/annotations. Each loader runs hooks in this order:

* `@onInit`: before runtime annotation code.
* `@annotationInit`: registers a handler function for a retained annotation.
* `@onPostInit`: after retained annotations are handled. These hooks are run in parallel with `task.spawn`.

Server and client init files both receive shared runtime data. There is no separate shared init file.

??? example "Loader Code"
    ```lua title="AnnotationInit.x.lua"
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
        task.spawn(fun, manifest)
    end
    ```

## Manifest data
The manifest is built from annotations and extension output. The core manifest contains these keys:

* `anot_hooks`: a map of annotation names to runtime handler functions.
* `init_hooks`: functions annotated with `@onInit`.
* `post_init_hooks`: functions annotated with `@onPostInit`.
* `annotations`: parsed annotations whose `retention` is not `build`.

Each annotation in `manifest.annotations` is converted into a lua table with:

* `name`: the annotation name.
* `args`: parsed positional arguments.
* `kwargs`: parsed keyword arguments.
* `getAdornee`: a function that returns the annotated module, method, or value.
* any extra data written to `annotation.export_data` by python build code.

For example, the networking extension writes `remote_name` and `remote_parent` during build, so its runtime handler can find the generated Roblox remote instance.

## Retention
`AnnotationDef.retention` controls whether an annotation is placed in the runtime manifest.

```python
AnnotationDef(
    'myRuntimeAnnotation',
    scope='method',
    retention='init',
)
```

`build` is the default and means the annotation is only used by python build hooks.

`init` and `runtime` are both included in `manifest.annotations`.

!!! note
    Currently `runtime` and `init` are effectively the same. There are plans to make `runtime` emit annotation metadata into module tables.

## Defining runtime effects
Runtime annotation effects usually have two parts:

1. A python extension registers the annotation with `retention='init'`.
2. The extension adds a lua runtime file which contains an `@annotationInit` handler with the same function name as the annotation.

`ctx.add_file(env, name, content)` writes generated runtime lua under `Generated/_Internal`. Files added this way are processed by the parser during the same build, so their `@annotationInit`, `@onInit`, and `@onPostInit` annotations are included in the manifest.

For example, this registers a `@addHelloWorld` method annotation that adds a function to the module table:

```python title="tools/print_effect.py"
from importlib.resources import files
from lua_annotations.api.annotations import AnnotationDef, Extension, ExtensionRegistry


class HelloWorldExtension(Extension):
    def load(self, ctx: ExtensionRegistry):
        ctx.register_anot(AnnotationDef('addHelloWorld', retention='init'))

        runtime_file = files('my_package') / 'lua' / 'MyAnnotations.lua'
        ctx.add_file('shared', 'MyAnnotations.lua', runtime_file.read_text())


def load(ctx: ExtensionRegistry):
    ctx.register_extension(PrintEffectExtension())
```

And the lua runtime file:

```lua title="MyAnnotations.lua"
--@annotationInit
local function addHelloWorld(anot, manifest)
    local module = anot.getAdornee()
    module.helloWorld = function()
        print("Hello World!")
    end
end

return {
    addHelloWorld = addHelloWorld,
}
```

Now a project file can use the runtime annotation, and the `helloWorld` function will be added automatically.

## Adding build-time data
Runtime handlers often need data that is easier to compute in python. Use the annotation's `export_data` dictionary inside an `on_build` callback.

```python
from lua_annotations.api.annotations import AnnotationBuildCtx, AnnotationDef, Extension, ExtensionRegistry
from lua_annotations.parser_schemas import LuaMethod


class SignalExtension(Extension):
    def on_build_signal(self, ctx: AnnotationBuildCtx):
        method = ctx.annotation.adornee
        assert isinstance(method, LuaMethod)

        ctx.annotation.export_data['method_name'] = method.name
        ctx.annotation.export_data['module_name'] = method.module.returned_name

    def load(self, ctx: ExtensionRegistry):
        ctx.register_anot(
            AnnotationDef(
                'signal',
                scope='method',
                retention='init',
                on_build=self.on_build_signal,
            )
        )
```

The lua handler can then read `anot.method_name` and `anot.module_name`.