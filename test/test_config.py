import json

import pytest  # pyright: ignore[reportMissingImports]

import lua_annotations.config as config_mod
from lua_annotations.exceptions import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)


def test_read_config_parses_named_workspaces_optional_extensions_and_tests(tmp_path):
    config_file = tmp_path / 'annotations.config.json'
    config_file.write_text(
        json.dumps(
            {
                'outDirName': 'Generated',
                'workspace_common': {
                    'shared': {'src/common/shared': ':Common'},
                },
                'workspaces': {
                    'game': {
                        'client': {'src/client': ':'},
                        'server': {'src/server': ':'},
                        'shared': {'src/shared': ':'},
                    }
                },
                'extensions': [['library', 'lua_annotations.extensions.game_framework.main']],
                'optional_extensions': {
                    'unit-test': ['library', 'lua_annotations.extensions.unit_tests.main'],
                },
                'tests': {
                    'root': 'spec',
                    'outDirName': 'Build',
                },
            }
        )
    )

    config = config_mod.read_config(config_file)

    assert isinstance(config, config_mod.Config)
    assert list(config.workspaces.keys()) == ['game']
    assert config.workspaces['game'].shared == {'src/shared': ':', 'src/common/shared': ':Common'}
    assert config.optional_extensions['unit-test'].expr == 'lua_annotations.extensions.unit_tests.main'
    assert config.tests == config_mod.TestsConfig(root='spec', out_dir_name='Build')


def test_read_config_rejects_list_style_workspaces(tmp_path):
    config_file = tmp_path / 'annotations.config.json'
    config_file.write_text(
        json.dumps(
            {
                'workspaces': [
                    {
                        'client': {'src/client': ':'},
                        'server': {'src/server': ':'},
                        'shared': {'src/shared': ':'},
                    }
                ]
            }
        )
    )

    with pytest.raises(ConfigValidationError, match='list-style workspaces'):
        config_mod.read_config(config_file)


def test_read_config_applies_workspace_common_to_each_named_workspace(tmp_path):
    config_file = tmp_path / 'annotations.config.json'
    config_file.write_text(
        json.dumps(
            {
                'workspace_common': {
                    'client': {'src/common/client': ':Common'},
                    'server': {'src/common/server': ':Common'},
                    'shared': {'src/common/shared': ':Common'},
                },
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
                },
            }
        )
    )

    config = config_mod.read_config(config_file)

    assert config.workspaces['hub'].client == {'src/hub/client': ':', 'src/common/client': ':Common'}
    assert config.workspaces['game'].shared == {'src/game/shared': ':', 'src/common/shared': ':Common'}


def test_selected_extensions_support_repeatable_names_and_all(tmp_path):
    config_file = tmp_path / 'annotations.config.json'
    config_file.write_text(
        json.dumps(
            {
                'workspaces': {
                    'game': {
                        'client': {'src/client': ':'},
                        'server': {'src/server': ':'},
                        'shared': {'src/shared': ':'},
                    }
                },
                'extensions': [['library', 'lua_annotations.extensions.game_framework.main']],
                'optional_extensions': {
                    'unit-test': ['library', 'lua_annotations.extensions.unit_tests.main'],
                    'other': {'kind': 'path', 'expr': 'tools/ext.py'},
                },
            }
        )
    )

    config = config_mod.read_config(config_file)

    assert [ext.expr for ext in config.selected_extensions([])] == ['lua_annotations.extensions.game_framework.main']
    assert [ext.expr for ext in config.selected_extensions(['unit-test'])] == [
        'lua_annotations.extensions.game_framework.main',
        'lua_annotations.extensions.unit_tests.main',
    ]
    assert [ext.expr for ext in config.selected_extensions(['all'])] == [
        'lua_annotations.extensions.game_framework.main',
        'lua_annotations.extensions.unit_tests.main',
        'tools/ext.py',
    ]


def test_selected_extensions_reject_unknown_optional_extension(tmp_path):
    config_file = tmp_path / 'annotations.config.json'
    config_file.write_text(
        json.dumps(
            {
                'workspaces': {
                    'game': {
                        'client': {'src/client': ':'},
                        'server': {'src/server': ':'},
                        'shared': {'src/shared': ':'},
                    }
                }
            }
        )
    )

    config = config_mod.read_config(config_file)
    with pytest.raises(ConfigValidationError, match='unknown optional extension'):
        config.selected_extensions(['missing'])


def test_read_config_raises_file_not_found_error(tmp_path):
    with pytest.raises(ConfigFileNotFoundError):
        config_mod.read_config(tmp_path / 'missing.config.json')


def test_read_config_raises_parse_error_for_invalid_json(tmp_path):
    config_file = tmp_path / 'annotations.config.json'
    config_file.write_text('{"outDirName": ')

    with pytest.raises(ConfigParseError):
        config_mod.read_config(config_file)
