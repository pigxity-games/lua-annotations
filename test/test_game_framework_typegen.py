from pathlib import Path
from textwrap import dedent

import pytest  # pyright: ignore[reportMissingImports]

from lua_annotations.api.annotations import ENVIRONMENTS, ExtensionRegistry
from lua_annotations.build_process import BuildProcessCtx, Environment, PostProcessCtx, Workspace
from lua_annotations.config import Config
from lua_annotations.exceptions import BuildError
from lua_annotations.extensions import default as default_ext
from lua_annotations.extensions.game_framework import main as game_framework_ext


def write_lua(tmp_path: Path, relative_path: str, text: str):
    file = tmp_path / relative_path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(dedent(text).strip() + '\n')


def build_service_types(tmp_path: Path, files: dict[str, str]):
    for relative_path, text in files.items():
        write_lua(tmp_path, relative_path, text)

    workspace: Workspace = {
        'client': {
            tmp_path / 'client' / 'src': ':.',
        },
        'server': {
            tmp_path / 'server' / 'src': ':.',
        },
        'shared': {
            tmp_path / 'shared' / 'src': ':.',
        },
    }

    reg = ExtensionRegistry()
    default_ext.load(reg)
    game_framework_ext.load(reg)
    sorted_reg = reg.sort_extensions()
    config = Config(out_dir_name='Generated')

    build_ctxs: dict[Environment, BuildProcessCtx] = {}
    for env in ENVIRONMENTS:
        root = tmp_path / env
        source_root = root / 'src'
        source_root.mkdir(parents=True, exist_ok=True)

        output_root = root / 'Generated'
        output_root.mkdir(parents=True, exist_ok=True)

        build_ctx = BuildProcessCtx(sorted_reg, root, workspace, config, 'test', workspace[env], output_root, env)
        build_ctx.process_dir(source_root)
        build_ctxs[env] = build_ctx

    post_ctx = PostProcessCtx(sorted_reg, tmp_path, workspace, config, 'test', build_ctxs)
    for hook in sorted_reg.post_build_hooks:
        hook(post_ctx)

    return {env: (tmp_path / env / 'Generated' / 'ServiceTypes.lua').read_text() for env in ENVIRONMENTS}


def test_service_types_include_remote_dependency_alias_and_remote_only_methods(tmp_path: Path):
    out = build_service_types(
        tmp_path,
        {
            'client/src/NotificationController.lua': '''
                --@service
                local controller = {}

                --@remote, event
                function controller.sendInfo(notification: Notification)
                end

                --@remote, function
                function controller.requestCount(player_id: number): number
                    return 0
                end

                function controller.localOnly(value: string)
                    return value
                end

                return controller
            ''',
            'server/src/LoggerService.lua': '''
                --@service
                local service = {}

                return service
            ''',
            'server/src/PartyService.lua': '''
                --@service, depends=[LoggerService, client:NotificationController]
                local service = {}

                return service
            ''',
        },
    )['server']

    assert 'export type NotificationController = {' in out
    assert '    sendInfo: (Notification) -> (),' in out
    assert '    requestCount: (number) -> (number),' in out
    assert 'localOnly' not in out
    assert 'export type PartyServiceDeps = {LoggerService: LoggerService, NotificationController: NotificationController}' in out


def test_remote_dependency_type_overrides_same_named_local_type_in_output(tmp_path: Path):
    out = build_service_types(
        tmp_path,
        {
            'client/src/NotificationController.lua': '''
                --@dependency
                local module = {}

                --@remote, event
                function module.sendInfo(config: Notification)
                    notification(config)
                end

                function module.sendClickable(config: Notification, callback: () -> ())
                    local notif = notification(config)
                    notif.Hitbox.MouseButton1Click:Connect(callback)
                end

                return module
            ''',
            'server/src/NotificationController.lua': '''
                --@dependency
                local module = {}

                function module.serverLocalOnly(config: Notification)
                    notification(config)
                end

                return module
            ''',
            'server/src/PartyService.lua': '''
                --@service, depends=[client:NotificationController]
                local service = {}

                return service
            ''',
        },
    )['server']

    assert 'export type NotificationController = {' in out
    assert '    sendInfo: (Notification) -> (),' in out
    assert 'sendClickable' not in out
    assert 'serverLocalOnly' not in out


def test_service_types_mirror_server_remote_function_types_into_client_output(tmp_path: Path):
    out = build_service_types(
        tmp_path,
        {
            'server/src/DataService.lua': '''
                --@service
                local service = {}

                --@remote, function
                function service.getProfile(user_id: number): PlayerProfile
                end

                function service.localOnly(user_id: number)
                    return user_id
                end

                return service
            ''',
            'client/src/ProfileController.lua': '''
                --@service, depends=[server:DataService]
                local controller = {}

                return controller
            ''',
        },
    )['client']

    assert 'export type DataService = {' in out
    assert '    getProfile: (number) -> (PlayerProfile),' in out
    assert 'localOnly' not in out
    assert 'export type ProfileControllerDeps = {DataService: DataService}' in out


def test_remote_dependency_errors_when_target_remote_module_does_not_exist(tmp_path: Path):
    with pytest.raises(BuildError, match='Invalid remote dependency for service.*MissingController'):
        build_service_types(
            tmp_path,
            {
                'server/src/PartyService.lua': '''
                    --@service, depends=[client:MissingController]
                    local service = {}

                    return service
                ''',
            },
        )
