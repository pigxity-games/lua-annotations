# lua-annotations-python

A lua annotation processor written in python; it's targeted toward Roblox development and is to be used as a modular game framework or simply a build-time processor.

### [Documentation](https://pigxity-games.github.io/lua-annotations)


## Key concepts
### Processor
- Expandable with an API
- Allows for functionality during build-time, runtime, or for both.

### Game framework
- Services (`@service`) define individual game logic
- Controllers (`@controller`) define per-instance behavior and are automatically mapped to instances containing CollectionService tags
- Dependency injection for services and controllers with automatic load ordering
- Seamless networking bridge; simply import "remote services" (wrappers of RemoteEvents/Functions) 

----


## CLI usage
To setup your project, run `lua-anot init path/to/project`. This creates a default config file. Don't forget to change the default environment paths if your project setup differs! 

This is mostly a CLI tool; to build a project, run this command: `lua-anot build path/to/project`. This command assumes the project directory contains a `annotations.config.json` file. You may specify a custom filename using the `--config` or `-c` argument.

The program also has a watch command, which detects changes and automatically rebuilds; used via `lua-anot watch`.

### Multiple workspaces
A workspace represents one individual place synced with rojo. Multi-place games would require using multiple.
It is also possible to have multiple paths per ennvironment, if you want to.

## Defining custom annotations
The program contains an easy API to do so!
```python
#Runs after annotation parsing
class MyExtension(Extension):
    def on_build_test_anot(ctx: AnnotationBuildCtx):
        print(f'Hello World, {ctx.annotation.name}!')

    #Runs after all files have been processed
    def on_post_process(ctx: PostProcessCtx):
        print('Build finished!')

    def load(ctx: ExtensionRegistry):
        ctx.register_anot(AnnotationDef('moduleTest', scope='module', on_build=self.on_build_test_anot)


def load(ctx: ExtensionRegistry):
    ctx.register_extension(MyExtension())
```

add it to your project's config file:
`annotations.config.json`
```json
extensions = [
    ["path", "my_extension/main.py"]
]
```

**Note: see the documentation for more info.**

**Since the project uses this API internally for optional extensions, you may also see the sourcecode under `/src/extensions/` for reference!**
