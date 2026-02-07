import json
from typing import Any
from annotations import AnnotationBuildCtx, AnnotationDef, AnnotationRegistry
from build_process import PostProcessCtx

REMOTE_STATE_KEY = 'default_extension.networking.remotes'

remoteInstanceMap = {
    'function': 'RemoteFunction',
    'event': 'RemoteEvent',
    'unreliable': 'UnreliableRemoteEvent',
}


def remote_on_build(ctx: AnnotationBuildCtx):
    anot = ctx.annotation

    className = remoteInstanceMap[ctx.annotation.args_val[0]]
    remotes: list[Any] = ctx.build_ctx.state.setdefault(REMOTE_STATE_KEY, [])
    remotes.append({'Name': f'{anot.adornee.module.name}_{ctx.annotation.adornee.name}', 'ClassName': className})


def post_process(ctx: PostProcessCtx):
    remotes = ctx.state.get(REMOTE_STATE_KEY, [])
    model = {'ClassName': 'Folder', 'Children': remotes}
    ctx.create_file('shared', 'Remotes.model.json', json.dumps(model))


def load(ctx: AnnotationRegistry):
    ctx.registerAnot(
        AnnotationDef('remote', scope='method', args=[str], on_build=remote_on_build)
    )
    ctx.onPostProcess(post_process)
