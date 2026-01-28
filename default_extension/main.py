from annotations import AnnotationBuildCtx, AnnotationDef, AnnotationRegistry
from default_extension import lifecycle, manifest, networking

class TestAnot(AnnotationDef):
    def test(self, ctx: AnnotationBuildCtx):
        print(ctx.annotation.adornee)

moduleTest = TestAnot('methodTest', scope='method')
methodTest = TestAnot('moduleTest', scope='module')

def load(ctx: AnnotationRegistry):
    ctx.registerAnot(moduleTest)
    ctx.registerAnot(methodTest)

    ctx.registerAnot(lifecycle.service)
    ctx.registerAnot(lifecycle.indexed)
    ctx.registerAnot(lifecycle.indexedType)
    
    ctx.registerAnot(networking.remote)
    ctx.onPostProcess(networking.post_process)
    ctx.onPostProcess(manifest.post_process)