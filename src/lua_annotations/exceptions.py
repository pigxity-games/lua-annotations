class LuaAnnotationsError(Exception):
    """Base class for general Lua Annotations errors."""


class BuildError(LuaAnnotationsError):
    """Raised for general build-time errors"""


class ConfigError(LuaAnnotationsError):
    """Raised for invalid project configuration."""


class ConfigFileError(ConfigError):
    """Raised for configuration file read/parse problems."""


class ConfigFileNotFoundError(ConfigFileError):
    """Raised when a config file path does not exist."""


class ConfigParseError(ConfigFileError):
    """Raised when a config file cannot be parsed as JSON."""


class ConfigValidationError(ConfigError):
    """Raised when config JSON shape or field values are invalid."""


class ParseError(LuaAnnotationsError):
    """Raised for invalid user-provided text."""
