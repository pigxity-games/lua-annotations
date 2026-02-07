from annotations import AnnotationRegistry
from build_process import PostProcessCtx

# TODO

client_manifest, server_manifest, shared_manifest = {}, {}, {}


def post_process(ctx: PostProcessCtx):
    ctx.create_file('client', 'Manifest.lua', '')
    ctx.create_file('server', 'Manifest.lua', '')
    ctx.create_file('shared', 'Manifest.lua', '')


def load(ctx: AnnotationRegistry):
    ctx.onPostProcess(post_process)
