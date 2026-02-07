from annotations import AnnotationRegistry
from default_extension import lifecycle, manifest, networking, test


def load(ctx: AnnotationRegistry):
    test.load(ctx)
    lifecycle.load(ctx)
    networking.load(ctx)
    manifest.load(ctx)
