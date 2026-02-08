from annotations import ENVIRONMENTS, AnnotationRegistry
from build_process import PostProcessCtx

# TODO

client_manifest, server_manifest, shared_manifest = {}, {}, {}


def post_process(ctx: PostProcessCtx):
    for env in ENVIRONMENTS:
        ctx.create_file(env, 'Manifest.lua', '')


def load(ctx: AnnotationRegistry):
    ctx.onPostProcess(post_process)
