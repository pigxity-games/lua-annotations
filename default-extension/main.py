from annotations import AnnotationDef, ExtensionContext

def customArg(v: str):
    return v * 2

moduleTest = AnnotationDef('methodTest',
    args=[int, str],
    kwargs={
        'test': customArg,
    })

methodTest = AnnotationDef('moduleTest')

def load(ctx: ExtensionContext):
    ctx.registerAnnotation(moduleTest)
    ctx.registerAnnotation(methodTest)