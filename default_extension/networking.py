from typing import Any

from api.annotations import AnnotationBuildCtx, AnnotationDef, AnnotationRegistry, Extension
from build_process import PostProcessCtx

REMOTE_INSTANCE_MAP = {
    'function': 'RemoteFunction',
    'event': 'RemoteEvent',
    'unreliable': 'UnreliableRemoteEvent',
}


class NetworkingExtension(Extension):
    def __init__(self):
        self.remotes: list[Any] = []


    def remote_on_build(self, ctx: AnnotationBuildCtx):
        anot = ctx.annotation

        class_name = REMOTE_INSTANCE_MAP[ctx.annotation.args_val[0]]
        self.remotes.append({'Name': f'{anot.adornee.module.returned_name}_{ctx.annotation.adornee.name}', 'ClassName': class_name})


    def on_post_process(self, ctx: PostProcessCtx):
        model = {'ClassName': 'Folder', 'Children': self.remotes}
        ctx.dump_json('shared', 'Remotes.model.json', model)


    def load(self, ctx: AnnotationRegistry):
        ctx.registerAnot(
            AnnotationDef('remote', scope='method', args=[str], on_build=self.remote_on_build)
        )
