from api.annotations import AnnotationDef, AnnotationRegistry


def load(ctx: AnnotationRegistry):
    ctx.registerAnot(AnnotationDef(
        'onPostInit',
        scope='method'
    ))
    ctx.registerAnot(AnnotationDef(
        name='annotationInit',
        scope='method'
    ))