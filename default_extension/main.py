from annotations import AnnotationBuildCtx, AnnotationDef, AnnotationRegistry

class TestAnnotation(AnnotationDef):
    def on_build(self, ctx: AnnotationBuildCtx):
        print(ctx)

moduleTest = TestAnnotation('methodTest')
methodTest = TestAnnotation('moduleTest', scope='method')

def load(ctx: AnnotationRegistry):
    ctx.register(moduleTest)
    ctx.register(methodTest)