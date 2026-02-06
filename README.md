A lua annotation processor written in python: it's targeted toward Roblox development and is to be used as a modular game framework or simply a build-time processor.

## Key concepts:
### Processor:
- Expandable with an API
- Allows for functionality during build-time, runtime, or for both.

### Game framework:
- Services (`@service`) define individual game logic
- Controllers (`@controller`) define per-instance behavior and are automatically mapped to instances containing CollectionService tags
- Dependency injection for services and controllers with automatic load ordering
- Seamless networking bridge; simply import "remote services" (wrappers of RemoteEvents/Functions)