# Exercises generated service types through the real parser and build hooks.
# These regressions keep static declarations aligned with dependency injection and remote senders.
from pathlib import Path
from textwrap import dedent

import pytest  # pyright: ignore[reportMissingImports]

from lua_annotations.api.annotations import ENVIRONMENTS, ExtensionRegistry
from lua_annotations.build_process import BuildProcessCtx, Environment, PostProcessCtx, Workspace
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

    build_ctxs: dict[Environment, BuildProcessCtx] = {}
    for env in ENVIRONMENTS:
        root = tmp_path / env
        source_root = root / 'src'
        source_root.mkdir(parents=True, exist_ok=True)

        output_root = root / 'Generated'
        output_root.mkdir(parents=True, exist_ok=True)

        build_ctx = BuildProcessCtx(sorted_reg, root, workspace, workspace[env], output_root, env)
        build_ctx.process_dir(source_root)
        build_ctxs[env] = build_ctx

    post_ctx = PostProcessCtx(sorted_reg, tmp_path, workspace, build_ctxs)
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
                function controller.sendInfo(notification: Notification): number
                    return 1
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

    assert 'export type ClientNotificationController = {' in out
    assert '    sendInfo: (Player | {Player} | "all", Notification) -> (),' in out
    assert '    requestCount: (Player, number) -> (number),' in out
    assert 'localOnly' not in out
    assert 'export type PartyServiceDeps = {LoggerService: LoggerService, client: {NotificationController: ClientNotificationController}}' in out


def test_remote_dependency_type_preserves_same_named_local_type_in_output(tmp_path: Path):
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

    assert 'export type ClientNotificationController = {' in out
    assert '    sendInfo: (Player | {Player} | "all", Notification) -> (),' in out
    assert 'sendClickable' not in out
    assert 'serverLocalOnly' in out
    assert 'export type NotificationController = {' in out
    assert 'export type ClientNotificationController = {' in out


def test_service_types_mirror_server_remote_function_types_into_client_output(tmp_path: Path):
    out = build_service_types(
        tmp_path,
        {
            'server/src/DataService.lua': '''
                --@service
                local service = {}

                --@remote, function
                function service.getProfile(player: Player, user_id: number): PlayerProfile
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

    assert 'export type ServerDataService = {' in out
    assert '    getProfile: (number) -> (PlayerProfile),' in out
    assert 'localOnly' not in out
    assert 'export type ProfileControllerDeps = {server: {DataService: ServerDataService}}' in out


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


def test_service_types_include_imported_types_declared_fields_and_colon_parameters(tmp_path: Path):
    out = build_service_types(
        tmp_path,
        {
            'server/src/State.lua': 'export type State = {ready: boolean}\nreturn {}',
            'server/src/Store.lua': 'local m = {}\nfunction m.new() return {} end\nreturn m',
            'server/src/MineService.lua': '''
                local State = require(script.Parent.State)
                local Store = require(script.Parent.Store)
                type Progress = {depth: number}
                --@service
                local MineService = {
                    data = Store.new(),
                    running = false,
                    depth = 1,
                    current = nil :: State.State?,
                }
                MineService.root = nil :: BasePart?
                function MineService.getState(): State.State
                end
                function MineService.enter(player: Player, depth: number)
                end
                function MineService:report(progress: Progress, depth: number): number
                    return depth
                end
                function MineService.identity(peer: MineService): MineService
                    return peer
                end
                return MineService
            ''',
        },
    )['server']

    assert 'local _ServerMineService_State = require(' in out
    assert '.MineService.Parent.State)' in out
    assert 'local _ServerMineService_Store = require(' in out
    assert 'type _ServerMineService_Progress = {depth: number}' in out
    assert 'data: typeof(_ServerMineService_Store.new())' in out
    assert 'running: boolean' in out
    assert 'depth: number' in out
    assert 'current: _ServerMineService_State.State?' in out
    assert 'root: BasePart?' in out
    assert 'getState: () -> (_ServerMineService_State.State)' in out
    assert 'enter: (Player, number) -> ()' in out
    assert 'report: (MineService, _ServerMineService_Progress, number) -> (number)' in out
    assert 'identity: (MineService) -> (MineService)' in out
    assert 'require(ServerScriptService.src.MineService)' not in out


def test_service_types_rebase_colliding_imports_without_importing_themselves(tmp_path: Path):
    out = build_service_types(
        tmp_path,
        {
            'client/src/NotificationController.lua': '''
                local Types = require(script.Parent.Types)
                --@service
                local controller = {}
                --@remote, unreliable
                function controller.send(info: Types.ClientInfo)
                end
                return controller
            ''',
            'server/src/NotificationController.lua': '''
                local Types = require(script.Parent.Types)
                local ST = require(game:GetService("ServerScriptService").Generated.ServiceTypes)
                local Unused = require(script.Parent.Unused)
                type Result = {Types: string, other: ST.NotificationController?}
                --@service, depends=[client:NotificationController]
                local controller = {
                    -- This comment must not swallow the following field.
                    running = false,
                }
                function controller.send(info: Types.ServerInfo): Result
                end
                return controller
            ''',
        },
    )['server']

    assert 'local _ClientNotificationController_Types = require(' in out
    assert 'local _ServerNotificationController_Types = require(' in out
    assert 'send: (Player | {Player} | "all", _ClientNotificationController_Types.ClientInfo)' in out
    assert 'send: (_ServerNotificationController_Types.ServerInfo)' in out
    assert 'running: boolean' in out
    assert '{Types: string, other: NotificationController?}' in out
    assert 'Generated.ServiceTypes)' not in out
    assert 'Unused' not in out


def test_service_types_preserve_literal_tokens_and_nested_casts(tmp_path: Path):
    out = build_service_types(
        tmp_path,
        {
            'server/src/TokenService.lua': '''
                local Store = require(script:WaitForChild("Store"))
                local ST = require(game:GetService("ServerScriptService").Generated.ServiceTypes)
                --@service
                local service = {
                    options = {Store = "ST.Ready", limit = nil :: number?},
                    data = Store.new(),
                }
                function service.status(): "ST.Ready" | ST.TokenService
                end
                return service
            ''',
        },
    )['server']

    assert 'options: typeof({Store = "ST.Ready", limit = nil :: number?})' in out
    assert 'status: () -> ("ST.Ready" | TokenService)' in out
    assert '.TokenService:WaitForChild("Store"))' in out
