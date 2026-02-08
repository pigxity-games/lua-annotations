# lua-annotations-python
A lua annotation processor written in python; it's targeted toward Roblox development and is to be used as a modular game framework or simply a build-time processor.

## Key concepts
### Processor
- Expandable with an API
- Allows for functionality during build-time, runtime, or for both.

### Game framework
- Services (`@service`) define individual game logic
- Controllers (`@controller`) define per-instance behavior and are automatically mapped to instances containing CollectionService tags
- Dependency injection for services and controllers with automatic load ordering
- Seamless networking bridge; simply import "remote services" (wrappers of RemoteEvents/Functions)

## CLI usage
To setup your project, run `lua-anot init path/to/project`. This creates a default config file. Don't forget to change the default environment paths if your project setup differs! 

This is mostly a CLI tool; to build a project, run this command: `lua-anot build path/to/project`. This command assumes the project directory contains a `annotations.config.json` file. You may specify a custom filename using the `--config` or `-c` argument.

The program also has a watch command, which detects changes and automatically rebuilds; used via `lua-anot watch`.

## Defining custom annotations
The program contains an easy API to do so! Simply define an extension in the config file:

```json
"extensions": {
    {
        "directory": "./my_extension"
        "entry":"./main.py"
    }
}
```
(`directory` path is relative to the project root; `entry` path is relative to the `directory` path)

In `main.py`, you can register annotations or build hooks with a `load()` function

```python
#Runs after annotation parsing
def test_anot(ctx: AnnotationBuildCtx):
    print(f'Hello World, {ctx.annotation.name}!')

#Runs after all files have been processed
def post_process(ctx: PostProcessCtx):
    print('Build finished!')


def load(ctx: AnnotationRegistry):
    ctx.registerAnot(AnnotationDef('moduleTest', scope='module', on_build=test_anot)
    ctx.onPostProcess(post_process)
```

**Since the project uses this API internally for built-in annotations, you may see the sourcecode under `/default_extension` for reference!**