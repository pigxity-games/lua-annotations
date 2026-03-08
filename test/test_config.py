import json

import pytest  # pyright: ignore[reportMissingImports]

from lua_annotations.config import Config, read_config
from lua_annotations.exceptions import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)


def test_read_config_parses_dataclasses_from_valid_json(tmp_path):
    config_file = tmp_path / "annotations.config.json"
    config_file.write_text(
        json.dumps(
            {
                "outDirName": "Generated",
                "workspaces": [
                    {
                        "client": {"src/client": ":"},
                        "server": {"src/server": ":"},
                        "shared": {"src/shared": ":"},
                    }
                ],
                "extensions": [["library", "lua_annotations.extensions.game_framework.main"]],
            }
        )
    )

    config = read_config(config_file)

    assert isinstance(config, Config)
    assert config.out_dir_name == "Generated"
    assert len(config.workspaces) == 1
    assert config.workspaces[0].client == {"src/client": ":"}
    assert config.workspaces[0].server == {"src/server": ":"}
    assert config.workspaces[0].shared == {"src/shared": ":"}
    assert len(config.extensions) == 1
    assert config.extensions[0].kind == "library"
    assert config.extensions[0].expr == "lua_annotations.extensions.game_framework.main"


def test_read_config_supports_object_style_extension_entries(tmp_path):
    config_file = tmp_path / "annotations.config.json"
    config_file.write_text(
        json.dumps(
            {
                "workspaces": [
                    {
                        "client": {"src/client": ":"},
                        "server": {"src/server": ":"},
                        "shared": {"src/shared": ":"},
                    }
                ],
                "extensions": [{"kind": "path", "expr": "tools/ext/main.py"}],
            }
        )
    )

    config = read_config(config_file)
    assert config.extensions[0].kind == "path"
    assert config.extensions[0].expr == "tools/ext/main.py"


def test_read_config_applies_workspace_common_to_each_workspace(tmp_path):
    config_file = tmp_path / "annotations.config.json"
    config_file.write_text(
        json.dumps(
            {
                "workspace_common": {
                    "client": {"src/common/client": ":Common"},
                    "server": {"src/common/server": ":Common"},
                    "shared": {
                        "src/common/shared": ":Common",
                        "wally@game-framework": ":Packages",
                    },
                },
                "workspaces": [
                    {
                        "client": {"src/client": ":"},
                        "server": {"src/server": ":"},
                        "shared": {"src/shared": ":"},
                    },
                    {
                        "client": {"src/client2": ":Project"},
                        "server": {"src/server2": ":Project"},
                        "shared": {"src/shared2": ":Project"},
                    },
                ],
            }
        )
    )

    config = read_config(config_file)

    ws1 = config.workspaces[0]
    assert ws1.client == {"src/client": ":", "src/common/client": ":Common"}
    assert ws1.server == {"src/server": ":", "src/common/server": ":Common"}
    assert ws1.shared == {
        "src/shared": ":",
        "src/common/shared": ":Common",
        "wally@game-framework": ":Packages",
    }

    ws2 = config.workspaces[1]
    assert ws2.client == {"src/client2": ":Project", "src/common/client": ":Common"}
    assert ws2.server == {"src/server2": ":Project", "src/common/server": ":Common"}
    assert ws2.shared == {
        "src/shared2": ":Project",
        "src/common/shared": ":Common",
        "wally@game-framework": ":Packages",
    }


def test_read_config_workspace_values_override_workspace_common(tmp_path):
    config_file = tmp_path / "annotations.config.json"
    config_file.write_text(
        json.dumps(
            {
                "workspace_common": {
                    "shared": {
                        "src/shared": ":CommonShared",
                        "src/common/shared": ":Common",
                    }
                },
                "workspaces": [
                    {
                        "client": {"src/client": ":"},
                        "server": {"src/server": ":"},
                        "shared": {"src/shared": ":"},
                    }
                ],
            }
        )
    )

    config = read_config(config_file)
    shared = config.workspaces[0].shared

    assert shared["src/shared"] == ":"
    assert shared["src/common/shared"] == ":Common"
    assert list(shared.keys())[0] == "src/shared"


def test_read_config_tracks_workspace_root_as_first_declared_env_path(tmp_path):
    config_file = tmp_path / "annotations.config.json"
    config_file.write_text(
        json.dumps(
            {
                "workspace_common": {
                    "client": {"src/common/client": ":Common"},
                    "server": {"src/common/server": ":Common"},
                    "shared": {"src/common/shared": ":Common"},
                },
                "workspaces": [
                    {
                        "client": {"src/client-root": ":", "src/client-extra": ":Extra"},
                        "server": {"src/server-root": ":", "src/server-extra": ":Extra"},
                        "shared": {"src/shared-root": ":", "src/shared-extra": ":Extra"},
                    }
                ],
            }
        )
    )

    config = read_config(config_file)
    workspace = config.workspaces[0]

    assert workspace.get_root("client") == "src/client-root"
    assert workspace.get_root("server") == "src/server-root"
    assert workspace.get_root("shared") == "src/shared-root"


def test_read_config_raises_file_not_found_error(tmp_path):
    with pytest.raises(ConfigFileNotFoundError):
        read_config(tmp_path / "missing.config.json")


def test_read_config_raises_parse_error_for_invalid_json(tmp_path):
    config_file = tmp_path / "annotations.config.json"
    config_file.write_text('{"outDirName": ')

    with pytest.raises(ConfigParseError):
        read_config(config_file)


def test_read_config_raises_validation_error_for_bad_workspace_shape(tmp_path):
    config_file = tmp_path / "annotations.config.json"
    config_file.write_text(
        json.dumps(
            {
                "workspaces": [
                    {
                        "client": {"src/client": ":"},
                        "server": {"src/server": ":"},
                    }
                ]
            }
        )
    )

    with pytest.raises(ConfigValidationError):
        read_config(config_file)


def test_read_config_raises_validation_error_for_bad_workspace_common_shape(tmp_path):
    config_file = tmp_path / "annotations.config.json"
    config_file.write_text(
        json.dumps(
            {
                "workspace_common": {
                    "shared": "src/common/shared",
                },
                "workspaces": [
                    {
                        "client": {"src/client": ":"},
                        "server": {"src/server": ":"},
                        "shared": {"src/shared": ":"},
                    }
                ],
            }
        )
    )

    with pytest.raises(ConfigValidationError):
        read_config(config_file)
