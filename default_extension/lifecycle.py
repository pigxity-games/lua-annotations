from annotations import AnnotationDef, AnnotationRegistry
from arguments import list_arg


def load(ctx: AnnotationRegistry):
    ctx.registerAnot(AnnotationDef('indexed', retention='build'))
    ctx.registerAnot(AnnotationDef('indexedType', scope='type', retention='build'))
    ctx.registerAnot(AnnotationDef('service', kwargs={'depends': list_arg}))
