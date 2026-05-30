## Project structure
An annotation processor for lua projects. see docs/ for documentation. The program scans through your project based on a config and extensions generate modules based on annotations / perform analysis.

### Key directories
- `src/lua_annotations/api`: public extension api
- `src/lua_annotations/extensions`: built-in extensions which use the api and the user may optionally enable.
- `src/lua_annotations/extensions/game_framework`: default game framework extension.
- `lua/`: lua packages for runtime extensions.

### Tooling (run these after code changes)
- run all unit tests: `pytest` **run pytest outside the sandbox**
- syntax check: `python -m py_compile {file}`
- type check: `pyright {file}`

The project also contains a luau test suite that uses `lune-test`.

```sh
lua-anot build test/luau/fixtures
lune run lune-test -m test/luau/manifest
```

## Code conventions
- use single quotes for strings ('') in python; luau code should use double quotes ("")
- use triple dobule quotes for docstrings ("""""")
    - only have docstrings for functions/classes accessed elsewhere (not module-private)
- code should be fully typed and checked with pyright. Avoid explicit function return types / variable types unless required to by the typechecker. (Types should be implicit unless required)
    - prefer simpler, functional solutions even if they are not type-safe if you are certain it would work as intended / the value would always be valid. Use asserts (peferred) or `#pyright: ignore[...]` comments if necessary.
- avoid large, monolithic functions/classes. Code should be split up into helper functions for easy reusability.
- prefer dataclasses for complex data types instead of dicts.