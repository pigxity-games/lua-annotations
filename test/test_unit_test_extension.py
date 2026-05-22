import json
from pathlib import Path
from textwrap import dedent

import pytest  # pyright: ignore[reportMissingImports]

from lua_annotations.api.annotations import ExtensionRegistry, SortedRegistry
from lua_annotations.build_process import BuildCtxList, BuildProcessCtx, PostProcessCtx, Workspace
from lua_annotations.config import read_config
from lua_annotations.extensions import default as default_ext
from lua_annotations.extensions.game_framework import main as game_framework_ext
from lua_annotations.extensions.unit_tests.main import UnitTestExtension

from helpers import make_build_ctxs


def write_file(root: Path, relative_path: str, text: str):
    file = root / relative_path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(dedent(text).strip() + '\n')


def make_post_ctx(project_root: Path, config_data: dict):
    config_file = project_root / 'annotations.config.json'
    config_file.write_text(json.dumps(config_data))
    config = read_config(config_file)

    workspace_cfg = next(iter(config.iter_workspaces()))
    workspace: Workspace = {
        'client': {project_root / path: expr for path, expr in workspace_cfg.client.items()},
        'server': {project_root / path: expr for path, expr in workspace_cfg.server.items()},
        'shared': {project_root / path: expr for path, expr in workspace_cfg.shared.items()},
    }
    build_ctxs = make_build_ctxs(project_root, workspace)
    return PostProcessCtx(SortedRegistry([], [], {}), project_root, workspace, config, workspace_cfg.name, build_ctxs)


def make_processed_post_ctx(project_root: Path, config_data: dict):
    config_file = project_root / 'annotations.config.json'
    config_file.write_text(json.dumps(config_data))
    config = read_config(config_file)

    registry = ExtensionRegistry()
    default_ext.load(registry)
    if any(ext.expr == 'lua_annotations.extensions.game_framework.main' for ext in config.extensions):
        game_framework_ext.load(registry)
    sorted_reg = registry.sort_extensions()

    workspace_cfg = next(iter(config.iter_workspaces()))
    workspace: Workspace = {
        'client': {project_root / path: expr for path, expr in workspace_cfg.client.items()},
        'server': {project_root / path: expr for path, expr in workspace_cfg.server.items()},
        'shared': {project_root / path: expr for path, expr in workspace_cfg.shared.items()},
    }

    build_ctxs: BuildCtxList = {}
    for env, rel_paths in workspace.items():
        root_dir = project_root / workspace_cfg.get_root(env)
        output_root = root_dir / config.out_dir_name
        output_root.mkdir(parents=True, exist_ok=True)
        build_ctx = BuildProcessCtx(sorted_reg, root_dir, workspace, config, workspace_cfg.name, rel_paths, output_root, env)
        for path in rel_paths:
            build_ctx.process_dir(path)
        build_ctxs[env] = build_ctx

    return PostProcessCtx(sorted_reg, project_root, workspace, config, workspace_cfg.name, build_ctxs)


def test_folder_convention_assigns_workspace_and_includes_common_mounts(tmp_path: Path):
    for path in (
        'src/hub/client',
        'src/hub/server',
        'src/hub/shared',
        'src/common/client',
        'src/common/server',
        'src/common/shared',
    ):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)

    write_file(
        tmp_path,
        'test/hub/foo_tests.lua',
        '''
            --@module
            local m = {}

            --@testCase
            function m.someCase()
            end

            return m
        ''',
    )

    post_ctx = make_post_ctx(
        tmp_path,
        {
            'workspaces': {
                'hub': {
                    'client': {'src/hub/client': ':'},
                    'server': {'src/hub/server': ':'},
                    'shared': {'src/hub/shared': ':'},
                }
            },
            'workspace_common': {
                'client': {'src/common/client': ':Common'},
                'server': {'src/common/server': ':Common'},
                'shared': {'src/common/shared': ':Common'},
            },
        },
    )

    manifest = UnitTestExtension()._build_manifest(post_ctx)

    assert 'workspace = "hub"' in manifest
    assert 'module = "./hub/foo_tests"' in manifest
    assert 'ReplicatedStorage = {' in manifest
    assert 'Common = "./src/common/shared"' in manifest
    assert '_root = "./src/hub/shared"' in manifest


def test_workspace_override_emits_prefixed_suites_for_multiple_workspaces(tmp_path: Path):
    for path in (
        'src/hub/client',
        'src/hub/server',
        'src/hub/shared',
        'src/game/client',
        'src/game/server',
        'src/game/shared',
    ):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)

    write_file(
        tmp_path,
        'test/common_tests.lua',
        '''
            --@module
            local m = {}

            --@testCase, workspaces=[hub, game]
            function m.someCase()
            end

            return m
        ''',
    )

    post_ctx = make_post_ctx(
        tmp_path,
        {
            'workspaces': {
                'hub': {
                    'client': {'src/hub/client': ':'},
                    'server': {'src/hub/server': ':'},
                    'shared': {'src/hub/shared': ':'},
                },
                'game': {
                    'client': {'src/game/client': ':'},
                    'server': {'src/game/server': ':'},
                    'shared': {'src/game/shared': ':'},
                },
            }
        },
    )

    manifest = UnitTestExtension()._build_manifest(post_ctx)

    assert 'hub_common_tests' in manifest
    assert 'game_common_tests' in manifest
    assert 'workspace = "hub"' in manifest
    assert 'workspace = "game"' in manifest


def test_multi_workspace_root_level_tests_require_explicit_workspaces(tmp_path: Path):
    for path in (
        'src/hub/client',
        'src/hub/server',
        'src/hub/shared',
        'src/game/client',
        'src/game/server',
        'src/game/shared',
    ):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)

    write_file(
        tmp_path,
        'test/common_tests.lua',
        '''
            --@module
            local m = {}

            --@testCase
            function m.someCase()
            end

            return m
        ''',
    )

    post_ctx = make_post_ctx(
        tmp_path,
        {
            'workspaces': {
                'hub': {
                    'client': {'src/hub/client': ':'},
                    'server': {'src/hub/server': ':'},
                    'shared': {'src/hub/shared': ':'},
                },
                'game': {
                    'client': {'src/game/client': ':'},
                    'server': {'src/game/server': ':'},
                    'shared': {'src/game/shared': ':'},
                },
            }
        },
    )

    with pytest.raises(Exception, match='must declare @testCase workspaces'):
        UnitTestExtension()._build_manifest(post_ctx)


def test_single_workspace_root_level_tests_are_allowed(tmp_path: Path):
    for path in ('src/game/client', 'src/game/server', 'src/game/shared'):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)

    write_file(
        tmp_path,
        'test/common_tests.lua',
        '''
            --@module
            local m = {}

            --@testCase
            function m.someCase()
            end

            return m
        ''',
    )

    post_ctx = make_post_ctx(
        tmp_path,
        {
            'workspaces': {
                'game': {
                    'client': {'src/game/client': ':'},
                    'server': {'src/game/server': ':'},
                    'shared': {'src/game/shared': ':'},
                }
            }
        },
    )

    manifest = UnitTestExtension()._build_manifest(post_ctx)
    assert 'common_tests' in manifest
    assert 'workspace = "game"' in manifest


def test_args_emit_raw_table_and_depends_emit_lazy_function(tmp_path: Path):
    for path in ('src/game/client', 'src/game/server', 'src/game/shared'):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)

    write_file(
        tmp_path,
        'src/game/server/TestService.lua',
        '''
            --@service
            local m = {}
            return m
        ''',
    )
    write_file(
        tmp_path,
        'test/game/service_tests.lua',
        '''
            --@module
            local m = {}

            --@testCase, args={12, 3, 4}
            function m.staticArgs()
            end

            --@testCase, depends=[TestService]
            function m.withDeps(deps)
            end

            return m
        ''',
    )

    post_ctx = make_post_ctx(
        tmp_path,
        {
            'workspaces': {
                'game': {
                    'client': {'src/game/client': ':'},
                    'server': {'src/game/server': ':'},
                    'shared': {'src/game/shared': ':'},
                }
            },
            'extensions': [['library', 'lua_annotations.extensions.game_framework.main']],
        },
    )

    manifest = UnitTestExtension()._build_manifest(post_ctx)

    assert 'staticArgs = {12, 3, 4}' in manifest
    assert 'withDeps = function() return createDependencies("game", {"TestService"}, false) end' in manifest


def test_depends_requires_game_framework(tmp_path: Path):
    for path in ('src/game/client', 'src/game/server', 'src/game/shared'):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)

    write_file(
        tmp_path,
        'test/game/service_tests.lua',
        '''
            --@module
            local m = {}

            --@testCase, depends=[TestService]
            function m.withDeps(deps)
            end

            return m
        ''',
    )

    post_ctx = make_post_ctx(
        tmp_path,
        {
            'workspaces': {
                'game': {
                    'client': {'src/game/client': ':'},
                    'server': {'src/game/server': ':'},
                    'shared': {'src/game/shared': ':'},
                }
            }
        },
    )

    with pytest.raises(Exception, match='game-framework extension is not loaded'):
        UnitTestExtension()._build_manifest(post_ctx)


def test_unit_test_extension_skips_non_annotated_workspace_modules_when_scanning_services(tmp_path: Path):
    for path in ('src/game/client', 'src/game/server', 'src/game/shared'):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)

    write_file(
        tmp_path,
        'src/game/shared/MineSettings.lua',
        '''
            local settings = {
                root = {},
            }

            return setmetatable(settings, {
                __index = settings.root,
            })
        ''',
    )
    write_file(
        tmp_path,
        'src/game/server/TestService.lua',
        '''
            --@service
            local m = {}
            return m
        ''',
    )
    write_file(
        tmp_path,
        'test/game/service_tests.lua',
        '''
            --@module
            local m = {}

            --@testCase, depends=[TestService]
            function m.withDeps(deps)
            end

            return m
        ''',
    )

    post_ctx = make_post_ctx(
        tmp_path,
        {
            'workspaces': {
                'game': {
                    'client': {'src/game/client': ':'},
                    'server': {'src/game/server': ':'},
                    'shared': {'src/game/shared': ':'},
                }
            },
            'extensions': [['library', 'lua_annotations.extensions.game_framework.main']],
        },
    )

    manifest = UnitTestExtension()._build_manifest(post_ctx)
    assert 'withDeps = function() return createDependencies("game", {"TestService"}, false) end' in manifest


def test_unit_test_extension_uses_processed_workspace_data_without_rescanning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for path in ('src/game/client', 'src/game/server', 'src/game/shared'):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)

    write_file(
        tmp_path,
        'src/game/server/TestService.lua',
        '''
            --@service
            local m = {}
            return m
        ''',
    )
    write_file(
        tmp_path,
        'test/game/service_tests.lua',
        '''
            --@module
            local m = {}

            --@testCase, depends=[TestService]
            function m.withDeps(deps)
            end

            return m
        ''',
    )

    post_ctx = make_processed_post_ctx(
        tmp_path,
        {
            'workspaces': {
                'game': {
                    'client': {'src/game/client': ':'},
                    'server': {'src/game/server': ':'},
                    'shared': {'src/game/shared': ':'},
                }
            },
            'extensions': [['library', 'lua_annotations.extensions.game_framework.main']],
        },
    )

    def fail_scan(*_args, **_kwargs):
        raise AssertionError('unit-test manifest should reuse processed workspace data')

    monkeypatch.setattr('lua_annotations.extensions.unit_tests.main._scan_service_graph', fail_scan)

    manifest = UnitTestExtension()._build_manifest(
        post_ctx,
        {'game': UnitTestExtension()._build_workspace_service_map(post_ctx)},
    )

    assert 'withDeps = function() return createDependencies("game", {"TestService"}, false) end' in manifest


def test_unit_test_manifest_only_emits_required_services(tmp_path: Path):
    for path in ('src/game/client', 'src/game/server', 'src/game/shared'):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)

    write_file(
        tmp_path,
        'src/game/shared/DataConfig.lua',
        '''
            --@dependency
            local config = {}
            return config
        ''',
    )
    write_file(
        tmp_path,
        'src/game/server/NeededService.lua',
        '''
            --@service, depends=[DataConfig]
            local m = {}
            return m
        ''',
    )
    write_file(
        tmp_path,
        'src/game/server/UnusedService.lua',
        '''
            --@service
            local m = {}
            return m
        ''',
    )
    write_file(
        tmp_path,
        'test/game/service_tests.lua',
        '''
            --@module
            local m = {}

            --@testCase, depends=[NeededService]
            function m.withDeps(deps)
            end

            return m
        ''',
    )

    post_ctx = make_processed_post_ctx(
        tmp_path,
        {
            'workspaces': {
                'game': {
                    'client': {'src/game/client': ':'},
                    'server': {'src/game/server': ':'},
                    'shared': {'src/game/shared': ':'},
                }
            },
            'extensions': [['library', 'lua_annotations.extensions.game_framework.main']],
        },
    )

    manifest = UnitTestExtension()._build_manifest(
        post_ctx,
        {'game': UnitTestExtension()._build_workspace_service_map(post_ctx)},
    )

    assert 'NeededService = {' in manifest
    assert 'DataConfig = {' in manifest
    assert 'UnusedService = {' not in manifest
