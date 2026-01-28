import json
from typing import TYPE_CHECKING
from annotations import AnnotationBuildCtx, AnnotationDef
from arguments import literal_builder

if TYPE_CHECKING:
    from dir_scan import BuildProcessCtx

remotes = []
class RemoteCreator(AnnotationDef):
    def on_build(self, ctx: AnnotationBuildCtx):
        className = 'RemoteFunction' if ctx.annotation.args_val[0] == 'function' else 'RemoteEvent'
        remotes.append({'Name': ctx.adornee.name, 'ClassName': className})

remote = RemoteCreator('remote', scope='method', args = [
    literal_builder(['function', 'event', 'unreliable'])
])

def post_process(ctx: BuildProcessCtx):
    model = {
        'ClassName': 'Folder',
        'Children': remotes
    }
    ctx.create_file('shared', 'Remotes.model.json', json.dumps(model))