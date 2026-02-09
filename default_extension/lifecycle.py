from annotations import AnnotationDef, AnnotationRegistry
from arguments import list_arg


def load(ctx: AnnotationRegistry):
    ctx.registerAnot(AnnotationDef('service', kwargs={'depends': list_arg}))
