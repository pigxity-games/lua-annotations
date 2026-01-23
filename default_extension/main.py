from annotations import AnnotationBuildCtx, AnnotationDef, AnnotationRegistry

class TestAnnotation(AnnotationDef):
    def on_build(self, ctx: AnnotationBuildCtx):
        print(ctx)

moduleTest = TestAnnotation('methodTest', scope='method')
methodTest = TestAnnotation('moduleTest', scope='module')

def load(ctx: AnnotationRegistry):
    ctx.register(moduleTest)
    ctx.register(methodTest)
