## Project structure
An annotation processor for lua projects. see docs/ for documentation. The program scans through your project based on a config and extensions generate modules based on annotations / perform analysis.

### Key directories
- `src/lua_annotations/api`: public extension api
- `src/lua_annotations/extensions`: built-in extensions which use the api and the user may optionally enable.
- `src/lua_annotations/extensions/game_framework`: default game framework extension.
- `lua/`: lua packages for runtime extensions.

### Testing
- run all unit tests: `python -m pytest`
- syntax check `python -m py_compile {file}`
- type check `pyright {file}`

## Code conventions
- use single quotes for strings ('')
- use triple dobule quotes for docstrings ("""""")
    - only have docstrings for functions/classes accessed elsewhere (not module-private)