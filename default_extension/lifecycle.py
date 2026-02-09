from api.annotations import AnnotationDef, AnnotationRegistry
from api.arguments import list_arg


def load(ctx: AnnotationRegistry):
    ctx.registerAnot(AnnotationDef('service', retention='runtime', kwargs={'depends': list_arg}))
