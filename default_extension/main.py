from annotations import AnnotationRegistry
from default_extension import lifecycle, test, index, networking


def load(ctx: AnnotationRegistry):
    test.load(ctx)
    ctx.registerExtension(index.IndexExtension())
    lifecycle.load(ctx)
    ctx.registerExtension(networking.NetworkingExtension())
