from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dir_scan import BuildProcessCtx

client_manifest, server_manifest, shared_manifest = {}, {}, {}

def post_process(ctx: BuildProcessCtx):
    ctx.create_file('client', 'Manifest.lua', '')
    ctx.create_file('server', 'Manifest.lua', '')
    ctx.create_file('shared', 'Manifest.lua', '')