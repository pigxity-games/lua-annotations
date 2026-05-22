from collections.abc import Iterable
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Literal

from .exceptions import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)

type Environment = Literal['server', 'client', 'shared']
type ExtensionKind = Literal['library', 'path']
type PathMap = dict[str, str]
type WorkspaceMaps = dict[Environment, PathMap]
type WorkspaceRoots = dict[Environment, str]
ENV_KEYS: tuple[Environment, ...] = ('client', 'server', 'shared')


def _validation_error(message: str, field_path: str) -> ConfigValidationError:
    return ConfigValidationError(f'{field_path}: {message}')


def _parse_path_map(raw: Any, field_path: str) -> PathMap:
    if not isinstance(raw, dict):
        raise _validation_error('expected an object mapping paths to lua expressions', field_path)

    out: PathMap = {}
    for key, value in raw.items():
        if not isinstance(key, str) or key.strip() == '':
            raise _validation_error('path key must be a non-empty string', field_path)
        if not isinstance(value, str) or value.strip() == '':
            raise _validation_error('lua expression must be a non-empty string', field_path)
        out[key] = value

    if len(out) == 0:
        raise _validation_error('must contain at least one mapped path', field_path)
    return out


def _parse_environment_maps(raw: dict[str, Any], field_path: str, require_all: bool):
    parsed: WorkspaceMaps = {env: {} for env in ENV_KEYS}
    for env in ENV_KEYS:
        if env not in raw:
            if require_all:
                raise _validation_error(f'missing required environment `{env}`', field_path)
            continue
        parsed[env] = _parse_path_map(raw[env], f'{field_path}.{env}')
    return parsed


def _merge_path_maps(workspace_paths: PathMap, common_paths: PathMap):
    merged = dict(workspace_paths)
    for path, expr in common_paths.items():
        merged.setdefault(path, expr)
    return merged


def _parse_extension_config(raw: Any, field_path: str):
    kind: Any
    expr: Any

    if isinstance(raw, (tuple, list)):
        if len(raw) != 2:
            raise _validation_error('tuple/list extension must have 2 items', field_path)
        kind, expr = raw
    elif isinstance(raw, dict):
        kind = raw.get('kind')
        expr = raw.get('expr')
    else:
        raise _validation_error('expected a 2-item list/tuple or an object', field_path)

    if kind not in ('library', 'path'):
        raise _validation_error('kind must be `library` or `path`', field_path)
    if not isinstance(expr, str) or expr.strip() == '':
        raise _validation_error('expr must be a non-empty string', field_path)

    return ExtensionConfig(kind, expr)


def _parse_named_extensions(raw: Any, field_path: str):
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _validation_error('must be an object', field_path)

    out: dict[str, ExtensionConfig] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or name.strip() == '':
            raise _validation_error('extension name must be a non-empty string', field_path)
        out[name] = _parse_extension_config(value, f'{field_path}.{name}')
    return out


@dataclass(frozen=True)
class WorkspaceConfig:
    name: str
    client: PathMap
    server: PathMap
    shared: PathMap
    client_root: str
    server_root: str
    shared_root: str

    def get(self, env: Environment) -> PathMap:
        return getattr(self, env)

    def get_root(self, env: Environment) -> str:
        return getattr(self, f'{env}_root')

    @classmethod
    def from_raw(cls, name: str, raw: Any, common: WorkspaceMaps):
        field_path = f'workspaces.{name}'
        if not isinstance(raw, dict):
            raise _validation_error('expected an object', field_path)

        parsed = _parse_environment_maps(raw, field_path, require_all=True)
        roots: WorkspaceRoots = {env: next(iter(parsed[env].keys())) for env in ENV_KEYS}
        merged: WorkspaceMaps = {env: _merge_path_maps(parsed[env], common[env]) for env in ENV_KEYS}
        return cls(
            name,
            merged['client'],
            merged['server'],
            merged['shared'],
            roots['client'],
            roots['server'],
            roots['shared'],
        )


@dataclass(frozen=True)
class ExtensionConfig:
    kind: ExtensionKind
    expr: str


@dataclass(frozen=True)
class TestsConfig:
    root: str = 'test'
    out_dir_name: str = 'Generated'

    @classmethod
    def from_raw(cls, raw: Any):
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise _validation_error('expected an object', 'tests')

        root = raw.get('root', 'test')
        out_dir_name = raw.get('outDirName', 'Generated')
        if not isinstance(root, str) or root.strip() == '':
            raise _validation_error('must be a non-empty string', 'tests.root')
        if not isinstance(out_dir_name, str) or out_dir_name.strip() == '':
            raise _validation_error('must be a non-empty string', 'tests.outDirName')
        return cls(root, out_dir_name)


@dataclass(frozen=True)
class Config:
    out_dir_name: str
    workspaces: dict[str, WorkspaceConfig] = field(default_factory=dict)
    extensions: list[ExtensionConfig] = field(default_factory=list)
    optional_extensions: dict[str, ExtensionConfig] = field(default_factory=dict)
    tests: TestsConfig = field(default_factory=TestsConfig)
    enabled_optional_extensions: tuple[str, ...] = ()

    def iter_workspaces(self) -> Iterable[WorkspaceConfig]:
        return self.workspaces.values()

    def selected_extensions(self, selected_optional: Iterable[str] | None = None):
        resolved = list(self.extensions)
        optional_names = list(self.optional_extensions.keys())
        selected = list(selected_optional or [])

        if 'all' in selected:
            resolved.extend(self.optional_extensions.values())
            return resolved

        unknown = [name for name in selected if name not in self.optional_extensions]
        if unknown:
            names = ', '.join(unknown)
            raise _validation_error(f'unknown optional extension(s): {names}', 'selected_extensions')

        for name in optional_names:
            if name in selected:
                resolved.append(self.optional_extensions[name])

        return resolved

    @classmethod
    def from_raw(cls, data: Any):
        if not isinstance(data, dict):
            raise _validation_error('expected top-level object', 'config')

        out_dir_name = data.get('outDirName', data.get('out_dir', 'Generated'))
        if not isinstance(out_dir_name, str) or out_dir_name.strip() == '':
            raise _validation_error('must be a non-empty string', 'outDirName')

        raw_workspace_common = data.get('workspace_common', {})
        if not isinstance(raw_workspace_common, dict):
            raise _validation_error('expected an object', 'workspace_common')
        workspace_common = _parse_environment_maps(raw_workspace_common, 'workspace_common', require_all=False)

        raw_workspaces = data.get('workspaces', {})
        if isinstance(raw_workspaces, list):
            raise _validation_error('must be an object of named workspaces; list-style workspaces are no longer supported', 'workspaces')
        if not isinstance(raw_workspaces, dict):
            raise _validation_error('must be an object', 'workspaces')

        workspaces: dict[str, WorkspaceConfig] = {}
        for name, raw_workspace in raw_workspaces.items():
            if not isinstance(name, str) or name.strip() == '':
                raise _validation_error('workspace name must be a non-empty string', 'workspaces')
            workspaces[name] = WorkspaceConfig.from_raw(name, raw_workspace, workspace_common)

        raw_extensions = data.get('extensions', [])
        if not isinstance(raw_extensions, list):
            raise _validation_error('must be a list', 'extensions')
        extensions = [_parse_extension_config(raw, f'extensions[{i}]') for i, raw in enumerate(raw_extensions)]

        optional_extensions = _parse_named_extensions(data.get('optional_extensions'), 'optional_extensions')
        tests = TestsConfig.from_raw(data.get('tests'))

        return cls(out_dir_name, workspaces, extensions, optional_extensions, tests)


def read_config(config_file: Path):
    if not config_file.exists():
        raise ConfigFileNotFoundError('Config file not found. Run the program in init mode to create one!')

    try:
        data = json.loads(config_file.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigParseError(f'Invalid JSON in {config_file}: line {exc.lineno}, column {exc.colno}: {exc.msg}') from exc

    return Config.from_raw(data)
