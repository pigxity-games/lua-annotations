from pathlib import Path, PurePath
from dataclasses import dataclass, field
import threading
from typing import Any, cast

from lua_annotations.api.annotations import AnnotationDef, Extension, ExtensionRegistry, SortedRegistry
from lua_annotations.api.arguments import bool_arg, default_list
from lua_annotations.api.lua_dict import LuaExpr, LuaPathResolver, convert_dict
from lua_annotations.annotation_meta_parse import AnnotationMeta, META_FILE_NAME
from lua_annotations.build_process import BuildProcessCtx, Environment, PostProcessCtx, get_template
from lua_annotations.exceptions import BuildError
from lua_annotations.parser import FileParser
from lua_annotations.parser_schemas import ANNOTATION_PREFIX
from lua_annotations.parser_schemas import Annotation, LuaMethod

from .. import default as default_ext
from ..game_framework import main as game_framework_ext

ENV_TO_SERVICE = {
    'shared': 'ReplicatedStorage',
    'server': 'ServerScriptService',
    'client': 'PlayerScripts',
}


@dataclass
class ServiceModuleInfo:
    env: Environment
    path: list[str]
    depends: list[str]
    kind: str

    def as_manifest_dict(self):
        return {
            'env': self.env,
            'path': self.path,
            'depends': self.depends,
            'kind': self.kind,
        }


@dataclass
class ManifestBuildState:
    expected_workspaces: set[str]
    workspace_service_maps: dict[str, dict[str, ServiceModuleInfo]] = field(default_factory=dict)
    written: bool = False


def _table_arg(value: str):
    value = value.strip()
    if not (value.startswith('{') and value.endswith('}')):
        raise BuildError('@testCase args must be a Lua table literal wrapped in `{}`')
    return value


def _suite_key(relative_path: PurePath, workspace_name: str | None = None):
    base = '_'.join(relative_path.with_suffix('').parts)
    safe = ''.join(char if char.isalnum() or char == '_' else '_' for char in base)
    if workspace_name is None:
        return safe
    return f'{workspace_name}_{safe}'


def _module_path(relative_path: PurePath):
    return './' + relative_path.with_suffix('').as_posix()


def _expr_to_mount_path(expr: str):
    expr = expr.strip()
    if not expr.startswith(':'):
        raise BuildError(f'unit-test mount expression must start with `:`; got {expr!r}')
    suffix = expr[1:]
    if suffix == '':
        return ['_root']
    return [part for part in suffix.split('.') if part]


def _inline_string_list(values: list[str]):
    inner = ', '.join(f'"{value}"' for value in values)
    return '{' + inner + '}'


def _insert_mount(target: dict[str, Any], expr: str, value: str):
    current = target
    parts = _expr_to_mount_path(expr)
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _longest_match(file: Path, workspace_cfg, workdir: Path):
    matches: list[tuple[int, Path, str]] = []
    for env in ('client', 'server', 'shared'):
        for raw_path, expr in workspace_cfg.get(env).items():
            root = workdir / raw_path
            try:
                relative = file.relative_to(root)
                matches.append((len(root.parts), relative, f'{env}:{expr}'))
            except ValueError:
                continue

    if not matches:
        raise BuildError(f'File {file.as_posix()} does not belong to workspace `{workspace_cfg.name}`')
    _, relative, encoded = max(matches, key=lambda item: item[0])
    env, expr = encoded.split(':', 1)
    return env, expr, relative


def _module_locator_parts(file: Path, workspace_cfg, workdir: Path):
    env, expr, relative = _longest_match(file, workspace_cfg, workdir)
    expr_parts = [part for part in _expr_to_mount_path(expr) if part != '_root']
    rel_parts = list(relative.with_suffix('').parts)
    return env, expr_parts + rel_parts


def _make_registry(include_game_framework: bool):
    registry = ExtensionRegistry()
    default_ext.load(registry)
    if include_game_framework:
        game_framework_ext.load(registry)
    return registry.sort_extensions()


def _make_test_registry():
    registry = ExtensionRegistry()
    default_ext.load(registry)
    load(registry)
    return registry.sort_extensions()


def _make_workspace_mapping(workdir: Path, workspace_cfg):
    workspace = {}
    for env in ('client', 'server', 'shared'):
        env_paths = {}
        for raw_path, expr in workspace_cfg.get(env).items():
            env_paths[workdir / raw_path] = expr
        workspace[env] = env_paths
    return workspace


def _parse_file(reg: SortedRegistry, file: Path, root_dir: Path, workspace, config, workspace_name: str, env: Environment):
    parser = FileParser(reg, file, BuildProcessCtx(reg, root_dir, workspace, config, workspace_name, workspace[env], root_dir, env))
    parser.parse(file.read_text())
    return parser


def _load_parser_text(file: Path):
    text = file.read_text()
    meta_file = file.parent / META_FILE_NAME
    if meta_file.exists():
        text = AnnotationMeta(meta_file).process(text)
    return text


def _scan_service_graph(workdir: Path, config, workspace_cfg):
    registry = _make_registry(True)
    workspace = _make_workspace_mapping(workdir, workspace_cfg)
    entries: dict[str, ServiceModuleInfo] = {}

    for env in ('client', 'server', 'shared'):
        root = workdir / workspace_cfg.get_root(env)
        for base_dir in workspace[env].keys():
            for file in base_dir.rglob('*'):
                if not file.is_file() or file.suffix not in ('.lua', '.luau'):
                    continue
                if config.out_dir_name in file.parts:
                    continue
                text = _load_parser_text(file)
                if ANNOTATION_PREFIX not in text:
                    continue

                parser = FileParser(
                    registry,
                    file,
                    BuildProcessCtx(registry, root, workspace, config, workspace_cfg.name, workspace[env], root, env),
                )
                parser.parse(text)
                for annotation in parser.annotations:
                    if annotation.name not in {'dependency', 'initService', 'service'}:
                        continue
                    env_name, path_parts = _module_locator_parts(file, workspace_cfg, workdir)
                    service_name = annotation.get_adornee_name()
                    assert isinstance(service_name, str)
                    entries[service_name] = ServiceModuleInfo(
                        env=cast(Environment, env_name),
                        path=path_parts,
                        depends=[dep for dep in annotation.kwargs_val.get('depends', []) if ':' not in dep],
                        kind=annotation.name,
                    )

    return entries


class UnitTestExtension(Extension):
    _state_lock = threading.Lock()
    _build_states: dict[int, ManifestBuildState] = {}

    def load(self, ctx: ExtensionRegistry):
        ctx.register_anot(
            AnnotationDef(
                'testCase',
                scope='method',
                kwargs={
                    'name': str,
                    'args': _table_arg,
                    'depends': default_list,
                    'skip_init': bool_arg,
                    'workspaces': default_list,
                },
            )
        )

    def on_post_process(self, ctx: PostProcessCtx):
        manifest = self._try_build_manifest(ctx)
        if manifest is None:
            return

        out_root = ctx.root_dir / ctx.config.tests.root / ctx.config.tests.out_dir_name
        out_root.mkdir(parents=True, exist_ok=True)
        (out_root / 'Manifest.lua').write_text(manifest)

    def _try_build_manifest(self, ctx: PostProcessCtx):
        if not self._include_game_framework(ctx):
            return self._build_manifest(ctx)

        build_key = id(ctx.config)
        workspace_services = self._build_workspace_service_map(ctx)

        with self._state_lock:
            state = self._build_states.setdefault(build_key, ManifestBuildState(set(ctx.config.workspaces.keys())))
            state.workspace_service_maps[ctx.workspace_name] = workspace_services

            if state.written or state.expected_workspaces - state.workspace_service_maps.keys():
                return None

            state.written = True
            service_maps = dict(state.workspace_service_maps)

        return self._build_manifest(ctx, service_maps)

    def _build_manifest(self, ctx: PostProcessCtx, workspace_service_maps: dict[str, dict[str, ServiceModuleInfo]] | None = None):
        test_root = ctx.root_dir / ctx.config.tests.root
        workspace_names = list(ctx.config.workspaces.keys())
        include_game_framework = self._include_game_framework(ctx)

        suites: dict[str, Any] = {}
        required_services = {name: set() for name in workspace_names}
        if test_root.is_dir():
            registry = _make_test_registry()
            for file in test_root.rglob('*'):
                if not file.is_file() or file.suffix not in ('.lua', '.luau'):
                    continue
                if ctx.config.tests.out_dir_name in file.parts:
                    continue
                self._collect_test_suites(
                    ctx,
                    registry,
                    file,
                    test_root,
                    workspace_names,
                    include_game_framework,
                    suites,
                    required_services,
                )

        service_name_map = self._build_required_service_map(ctx, include_game_framework, required_services, workspace_service_maps)

        manifest_data = {
            'workspaces': {name: {'mounts': self._build_mounts(workspace_cfg)} for name, workspace_cfg in ctx.config.workspaces.items()},
            'tests': suites,
        }

        template = get_template('Manifest.lua')
        resolver = LuaPathResolver({'server': {}, 'client': {}, 'shared': {}})
        service_map_lua = convert_dict(resolver, service_name_map)
        service_map_body = service_map_lua.removeprefix('return ').strip()
        manifest_lua = convert_dict(resolver, manifest_data)
        manifest_body = manifest_lua.removeprefix('return ').strip()
        return template.replace('--serviceNameMap', service_map_body).replace('--manifest', manifest_body)

    def _include_game_framework(self, ctx: PostProcessCtx):
        if any(ext.expr == 'lua_annotations.extensions.game_framework.main' for ext in ctx.config.extensions):
            return True

        for name in ctx.config.enabled_optional_extensions:
            ext = ctx.config.optional_extensions.get(name)
            if ext and ext.expr == 'lua_annotations.extensions.game_framework.main':
                return True

        return 'all' in ctx.config.enabled_optional_extensions and any(
            ext.expr == 'lua_annotations.extensions.game_framework.main' for ext in ctx.config.optional_extensions.values()
        )

    def _build_required_service_map(
        self,
        ctx: PostProcessCtx,
        include_game_framework: bool,
        required_services: dict[str, set[str]],
        workspace_service_maps: dict[str, dict[str, ServiceModuleInfo]] | None,
    ):
        if not include_game_framework:
            return {}

        service_maps = self._resolve_workspace_service_maps(ctx, workspace_service_maps)
        return {
            workspace_name: {
                service_name: info.as_manifest_dict()
                for service_name, info in self._collect_required_services(
                    workspace_name,
                    service_maps.get(workspace_name, {}),
                    required_services.get(workspace_name, set()),
                ).items()
            }
            for workspace_name in ctx.config.workspaces.keys()
        }

    def _resolve_workspace_service_maps(self, ctx: PostProcessCtx, workspace_service_maps: dict[str, dict[str, ServiceModuleInfo]] | None):
        if workspace_service_maps is None:
            return {
                workspace_cfg.name: _scan_service_graph(ctx.root_dir, ctx.config, workspace_cfg) for workspace_cfg in ctx.config.iter_workspaces()
            }

        missing = {workspace_cfg.name for workspace_cfg in ctx.config.iter_workspaces() if workspace_cfg.name not in workspace_service_maps}
        if not missing:
            return workspace_service_maps

        resolved = dict(workspace_service_maps)
        for workspace_cfg in ctx.config.iter_workspaces():
            if workspace_cfg.name in missing:
                resolved[workspace_cfg.name] = _scan_service_graph(ctx.root_dir, ctx.config, workspace_cfg)
        return resolved

    def _build_workspace_service_map(self, ctx: PostProcessCtx):
        workspace_cfg = ctx.config.workspaces[ctx.workspace_name]
        services: dict[str, ServiceModuleInfo] = {}

        for build_ctx in ctx.build_ctxs.values():
            for parser in build_ctx.parsed_files.values():
                self._collect_service_annotations(ctx.root_dir, workspace_cfg, parser, services)

        return services

    def _collect_service_annotations(
        self,
        workdir: Path,
        workspace_cfg,
        parser: FileParser,
        services: dict[str, ServiceModuleInfo],
    ):
        for annotation in parser.annotations:
            if annotation.name not in {'dependency', 'initService', 'service'}:
                continue

            service_name = annotation.get_adornee_name()
            assert isinstance(service_name, str)
            env_name, path_parts = _module_locator_parts(parser.file, workspace_cfg, workdir)
            services[service_name] = ServiceModuleInfo(
                env=cast(Environment, env_name),
                path=path_parts,
                depends=[dep for dep in annotation.kwargs_val.get('depends', []) if ':' not in dep],
                kind=annotation.name,
            )

    def _collect_required_services(
        self,
        workspace_name: str,
        workspace_services: dict[str, ServiceModuleInfo],
        requested_services: set[str],
    ):
        required: dict[str, ServiceModuleInfo] = {}
        visiting: set[str] = set()

        def visit(service_name: str):
            if service_name in required:
                return
            if service_name in visiting:
                raise BuildError(f'Cycle detected while collecting unit-test dependencies in workspace `{workspace_name}`: {service_name}')

            info = workspace_services.get(service_name)
            if info is None:
                raise BuildError(f'Unknown unit-test dependency `{service_name}` in workspace `{workspace_name}`')

            visiting.add(service_name)
            for dep_name in info.depends:
                visit(dep_name)
            visiting.remove(service_name)
            required[service_name] = info

        for service_name in sorted(requested_services):
            visit(service_name)

        return required

    def _build_mounts(self, workspace_cfg):
        mounts: dict[str, dict[str, Any]] = {
            'ReplicatedStorage': {},
            'ServerScriptService': {},
            'PlayerScripts': {},
        }

        for env, service_name in ENV_TO_SERVICE.items():
            for path, expr in workspace_cfg.get(env).items():
                _insert_mount(mounts[service_name], expr, './' + Path(path).as_posix())

        return mounts

    def _collect_test_suites(
        self,
        ctx: PostProcessCtx,
        registry: SortedRegistry,
        file: Path,
        test_root: Path,
        workspace_names: list[str],
        include_game_framework: bool,
        suites: dict[str, Any],
        required_services: dict[str, set[str]],
    ):
        relative = file.relative_to(test_root)
        workspace_hint = relative.parts[0] if relative.parts and relative.parts[0] in workspace_names else None
        parser = _parse_file(
            registry,
            file,
            test_root,
            {'shared': {test_root: ':'}, 'server': {}, 'client': {}},
            ctx.config,
            'tests',
            'shared',
        )

        cases = [annotation for annotation in parser.annotations if annotation.name == 'testCase']
        if not cases:
            return

        workspace_selection = self._resolve_test_workspaces(cases, relative, workspace_names, workspace_hint)
        for workspace_name in workspace_selection:
            case_entries = {}
            for annotation in cases:
                case_name, args_expr, case_depends = self._build_case(ctx, annotation, workspace_name, include_game_framework)
                case_entries[case_name] = args_expr
                required_services[workspace_name].update(case_depends)

            key_workspace = workspace_name if len(workspace_selection) > 1 else None
            suites[_suite_key(relative, key_workspace)] = {
                'workspace': workspace_name,
                'module': _module_path(relative),
                'cases': case_entries,
            }

    def _resolve_test_workspaces(self, cases: list[Annotation], relative: PurePath, workspace_names: list[str], workspace_hint: str | None):
        explicit = {workspace for annotation in cases for workspace in annotation.kwargs_val.get('workspaces', [])}

        if explicit:
            unknown = [name for name in explicit if name not in workspace_names]
            if unknown:
                raise BuildError(f'Unknown workspace(s) on @testCase in {relative.as_posix()}: {", ".join(unknown)}')
            return [name for name in workspace_names if name in explicit]

        if workspace_hint is not None:
            return [workspace_hint]

        if len(workspace_names) == 1:
            return workspace_names

        raise BuildError(f'Root-level test file {relative.as_posix()} must declare @testCase workspaces=[...] when multiple workspaces exist')

    def _build_case(self, ctx: PostProcessCtx, annotation: Annotation, workspace_name: str, include_game_framework: bool):
        adornee = annotation.adornee
        assert isinstance(adornee, LuaMethod)

        kwargs = annotation.kwargs_val
        if 'args' in kwargs and 'depends' in kwargs:
            raise BuildError(f'@testCase on {adornee.name} cannot use both `args` and `depends`')

        case_name = kwargs.get('name', adornee.name)
        if 'depends' in kwargs:
            if not include_game_framework:
                raise BuildError(f'@testCase depends on game-framework services, but the game-framework extension is not loaded: {adornee.name}')
            depends = kwargs.get('depends', [])
            skip_init = kwargs.get('skip_init', False)
            depends_lua = _inline_string_list(depends)
            expr = f'function() return createDependencies("{workspace_name}", {depends_lua}, {str(skip_init).lower()}) end'
            return case_name, LuaExpr(expr), depends

        if kwargs.get('skip_init', False):
            raise BuildError(f'@testCase skip_init requires depends=[...] on {adornee.name}')

        if 'args' in kwargs:
            return case_name, LuaExpr(kwargs['args']), []

        return case_name, LuaExpr('{}'), []


def load(ctx: ExtensionRegistry):
    ctx.register_extension(UnitTestExtension())
