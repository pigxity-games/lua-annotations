class LuaAnnotationsError(Exception):
    """Base class for general Lua Annotations errors."""


class BuildError(LuaAnnotationsError):
    """Raised for general build-time errors"""


class ConfigError(LuaAnnotationsError):
    """Raised for invalid project configuration."""


class ParseError(LuaAnnotationsError):
    """Raised for invalid user-provided text."""
