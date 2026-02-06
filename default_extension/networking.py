import json
from annotations import AnnotationBuildCtx, AnnotationDef
from build_process import BuildProcessCtx

remoteInstanceMap = {
    'function': 'RemoteFunction',
    'event': 'RemoteEvent',
    'unreliable': 'UnreliableRemoteEvent'
}

remotes = []
def on_build(ctx: AnnotationBuildCtx):
    className = remoteInstanceMap[ctx.annotation.args_val[0]]
    remotes.append({'Name': ctx.annotation.adornee.name, 'ClassName': className})

remote = AnnotationDef(
    'remote',
    scope='method',
    args = [str],
    on_build=on_build
)

def post_process(ctx: BuildProcessCtx):
    model = {
        'ClassName': 'Folder',
        'Children': remotes
    }
    ctx.create_file('shared', 'Remotes.model.json', json.dumps(model))