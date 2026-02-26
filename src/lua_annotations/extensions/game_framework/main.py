from api.annotations import ExtensionRegistry
from . import lifecycle, index, networking


def load(ctx: ExtensionRegistry):
    ctx.register_extension(index.IndexExtension())
    ctx.register_extension(lifecycle.LifecycleExtension(), deps=['ManifestExtension'], hook_order='before')
    ctx.register_extension(networking.NetworkingExtension())
