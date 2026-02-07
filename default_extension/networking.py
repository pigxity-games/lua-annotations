import json
from annotations import AnnotationBuildCtx, AnnotationDef
from build_process import BuildProcessCtx

REMOTE_STATE_KEY = 'default_extension.networking.remotes'

remoteInstanceMap = {
    'function': 'RemoteFunction',
    'event': 'RemoteEvent',
    'unreliable': 'UnreliableRemoteEvent'
}


def on_build(ctx: AnnotationBuildCtx):
    className = remoteInstanceMap[ctx.annotation.args_val[0]]
    remotes = ctx.build_ctx.state.setdefault(REMOTE_STATE_KEY, [])
    remotes.append({'Name': ctx.annotation.adornee.name, 'ClassName': className})


remote = AnnotationDef(
    'remote',
    scope='method',
    args=[str],
    on_build=on_build
)


def post_process(ctx: BuildProcessCtx):
    remotes = ctx.state.get(REMOTE_STATE_KEY, [])
    model = {
        'ClassName': 'Folder',
        'Children': remotes
    }
    ctx.create_file('shared', 'Remotes.model.json', json.dumps(model))
