from pathlib import Path
from textwrap import dedent

from importlib.resources import files

from lua_annotations.api.annotations import ENVIRONMENTS, ExtensionRegistry
from lua_annotations.build_process import BuildProcessCtx, Environment, PostProcessCtx, Workspace
from lua_annotations.exceptions import BuildError
from lua_annotations.extensions import default as default_ext
from lua_annotations.extensions.game_framework import main as game_framework_ext


def lifecycle_source():
    path = files('lua_annotations') / 'extensions' / 'game_framework' / 'lua' / 'Lifecycle.lua'
    return path.read_text()


def write_lua(tmp_path: Path, relative_path: str, text: str):
    file = tmp_path / relative_path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(dedent(text).strip() + '\n')


def build_generated(tmp_path: Path, files: dict[str, str]):
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

    return {env: {file.name: file.read_text() for file in (tmp_path / env / 'Generated').iterdir() if file.is_file()} for env in ENVIRONMENTS}


def test_middleware_annotations_and_remote_metadata_are_generated(tmp_path: Path):
    out = build_generated(
        tmp_path,
        {
            'server/src/Logger.lua': '''
                --@middleware, server, inbound, global=true
                local function Logger(ctx, ...)
                    return true, ...
                end

                return Logger
            ''',
            'server/src/AdminService.lua': '''
                --@service
                local service = {}

                --@remote, event, middleware=[Logger]
                function service.runAdminCommand(player: Player, command: string)
                    print(command)
                end

                return service
            ''',
        },
    )

    server_init = out['server']['AnnotationInit.server.lua']
    client_init = out['client']['AnnotationInit.client.lua']
    lifecycle = lifecycle_source()

    assert 'name = "middleware"' in server_init
    assert 'middleware_name = "Logger"' in server_init
    assert 'data = {' in server_init
    assert 'remotes = {' in server_init
    assert 'shared = {' not in server_init
    assert 'runAdminCommand' in server_init
    assert 'for remoteName, remoteInfo in pairs(serviceInfo) do' in lifecycle
    assert 'remotesTable[remoteName] = createRemoteSender(remoteInfo, remote)' in lifecycle
    assert '__index = function(t, remoteName)' not in lifecycle
    assert 'folder:GetChildren()' not in lifecycle
    assert 'remote_setup=' in lifecycle
    assert 'bound remote ' in lifecycle
    assert 'local isStudio = RunService:IsStudio()' in lifecycle
    assert 'if isStudio then' in lifecycle
    assert 'middleware = {' in server_init
    assert '"Logger"' in server_init
    assert 'runAdminCommand' in client_init


def test_runtime_template_includes_phase_timing(tmp_path: Path):
    out = build_generated(tmp_path, {})
    server_init = out['server']['AnnotationInit.server.lua']

    assert 'local initT0 = os.clock()' in server_init
    assert 'local annotationT0 = os.clock()' in server_init
    assert 'local postInitT0 = os.clock()' in server_init
    assert 'local isStudio = RunService and RunService:IsStudio()' in server_init
    assert 'if isStudio then' in server_init
    assert 'annotations loaded in ' in server_init
    assert 'post_init=' in server_init


def test_bind_tag_runtime_uses_no_cleanup_sentinel(tmp_path: Path):
    lifecycle = lifecycle_source()
    assert 'NO_CLEANUP' in lifecycle
    assert 'cleanups[inst] = NO_CLEANUP' in lifecycle
    assert 'bound tag ' in lifecycle


def test_shared_remote_annotations_are_invalid(tmp_path: Path):
    try:
        build_generated(
            tmp_path,
            {
                'shared/src/SharedService.lua': '''
                    --@service
                    local service = {}

                    --@remote, event
                    function service.badRemote()
                    end

                    return service
                ''',
            },
        )
    except BuildError as e:
        assert '@remote annotations are only valid in client or server code' in str(e)
    else:
        raise AssertionError('Expected shared @remote to raise BuildError')
