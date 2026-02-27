from pathlib import Path
from lua_annotations.api.annotations import ExtensionRegistry
from lua_annotations.parser import FileParser
import test.test_ext

if __name__ == '__main__':
    
    ctx = ExtensionRegistry()
    test.test_ext.load(ctx)
    ctx = ctx.sort_extensions()
    
    test_file = Path('./test/Test.lua')
    with test_file.open('r') as f:
        parser = FileParser(ctx, test_file, None)  # pyright: ignore[reportArgumentType]
        parser.parse(f.read())

    for module in parser.modules.values():
        print(module.name, module.returned_name)

    for anot in parser.annotations:
        print(anot.name, anot.adornee, anot.args_val, anot.kwargs_val)