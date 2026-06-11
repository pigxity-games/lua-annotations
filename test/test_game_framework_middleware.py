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


def manifest_functions_source():
    path = files('lua_annotations') / 'extensions' / 'game_framework' / 'lua' / 'ManifestFunctions.lua'
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
    pending_files = reg.pending_files
    sorted_reg = reg.sort_extensions()

    build_ctxs: dict[Environment, BuildProcessCtx] = {}
    for env in ENVIRONMENTS:
        root = tmp_path / env
        source_root = root / 'src'
        source_root.mkdir(parents=True, exist_ok=True)

        output_root = root / 'Generated'
        output_root.mkdir(parents=True, exist_ok=True)

        build_ctx = BuildProcessCtx(sorted_reg, root, workspace, workspace[env], output_root, env)
        for name, content in pending_files[env]:
            created = build_ctx.create_file('_Internal/' + name, content)
            build_ctx.process_file(created)
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

    server_manifest = out['server']['Manifest.lua']
    client_manifest = out['client']['Manifest.lua']
    lifecycle = lifecycle_source()
    manifest_api = (tmp_path / 'shared' / 'Generated' / '_Internal' / 'ManifestAPI.lua').read_text()

    assert 'name = "middleware"' in server_manifest
    assert 'middleware_name = "Logger"' in server_manifest
    assert 'data = {' in server_manifest
    assert 'remotes = {' in server_manifest
    assert 'shared = {' not in server_manifest
    assert 'getAdornee' not in server_manifest
    assert 'runAdminCommand' in server_manifest
    assert 'ManifestAPI.new({' in server_manifest
    assert 'require(ReplicatedStorage[\'Generated\']._Internal.ManifestAPI)' in server_manifest
    assert 'for remoteName, remoteInfo in pairs(serviceInfo) do' in lifecycle
    assert 'remotesTable[remoteName] = createRemoteSender(manifestApi, remoteInfo, remote)' in lifecycle
    assert '__index = function(t, remoteName)' not in lifecycle
    assert 'folder:GetChildren()' not in lifecycle
    assert 'bound remote ' in lifecycle
    assert 'manifestApi:getModule(moduleName)' in lifecycle
    assert 'local isStudio = RunService:IsStudio()' in lifecycle
    assert 'if isStudio then' in lifecycle
    assert 'middleware = {' in server_manifest
    assert '"Logger"' in server_manifest
    assert 'runAdminCommand' in client_manifest
    assert '--[[' in manifest_api
    assert 'local function waitForPath(path: ModulePath): Instance' in manifest_api
    assert 'function ManifestAPI:getModule(moduleName: string): any' in manifest_api
    assert 'Requires a generated module and caches its resolved export for future calls.' in manifest_api
    assert 'Requires a generated module and caches its resolved export for future calls.\n    @param moduleName' in manifest_api
    assert '@param moduleName The manifest module name to require from the generated module path map.' in manifest_api
    assert '@return The cached module value or requested export for the module.' in manifest_api
    assert 'Builds and returns the dependency table for the requested service or component.' in manifest_api
    assert 'Builds and returns the dependency table for the requested service or component.\n    @param serviceName' in manifest_api
    assert 'local function useCollectionTag(tag: string, consumer: (Instance) -> Cleanup?): ()' in manifest_api
    assert 'function ManifestAPI:getServiceDeps(serviceName: string, runDependencyInit: boolean?): ServiceDeps' in manifest_api
    assert '@param serviceName The manifest module name whose dependencies should be resolved.' in manifest_api
    assert '@param runDependencyInit When true or nil, dependent services are started before being injected. When false, dependencies are required without running their startup logic.' in manifest_api
    assert '@return A deps table containing resolved service dependencies and cross-environment remote wrappers keyed by their manifest names.' in manifest_api
    assert 'function ManifestAPI:getServiceDeps(' in manifest_api
    assert 'Starts and returns the requested service, component, initService, or dependency module.' in manifest_api
    assert '@param deps An optional dependency table to inject instead of building one with getServiceDeps.' in manifest_api
    assert 'function ManifestAPI:startService(serviceName: string, deps: ServiceDeps?): any' in manifest_api
    assert 'function ManifestAPI:startService(' in manifest_api


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


def test_default_manifest_does_not_include_game_framework_api(tmp_path: Path):
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
    sorted_reg = reg.sort_extensions()

    build_ctxs: dict[Environment, BuildProcessCtx] = {}
    for env in ENVIRONMENTS:
        root = tmp_path / env
        source_root = root / 'src'
        source_root.mkdir(parents=True, exist_ok=True)

        output_root = root / 'Generated'
        output_root.mkdir(parents=True, exist_ok=True)

        build_ctxs[env] = BuildProcessCtx(sorted_reg, root, workspace, workspace[env], output_root, env)

    post_ctx = PostProcessCtx(sorted_reg, tmp_path, workspace, build_ctxs)
    for hook in sorted_reg.post_build_hooks:
        hook(post_ctx)

    manifest = (tmp_path / 'client' / 'Generated' / 'Manifest.lua').read_text()
    manifest_api = (tmp_path / 'shared' / 'Generated' / '_Internal' / 'ManifestAPI.lua').read_text()
    assert 'ManifestAPI.new({' in manifest
    assert 'function m.startService(' not in manifest
    assert 'function m.getServiceDeps(' not in manifest
    assert 'function ManifestAPI:startService(' not in manifest_api
    assert 'function ManifestAPI:getServiceDeps(' not in manifest_api


def test_bind_tag_runtime_uses_no_cleanup_sentinel(tmp_path: Path):
    manifest_functions = manifest_functions_source()
    assert 'NO_CLEANUP' in manifest_functions
    assert 'cleanups[inst] = NO_CLEANUP' in manifest_functions
    assert 'bound tag ' in manifest_functions


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
