from annotations import AnnotationBuildCtx, AnnotationDef, AnnotationRegistry
from default_extension import lifecycle, manifest, networking

def test(ctx: AnnotationBuildCtx):
    print(f'Hello World, {ctx.annotation.name}!')

moduleTest = AnnotationDef('methodTest', scope='method', args=[str], kwargs={'testKwarg': str}, on_build=test)
methodTest = AnnotationDef('moduleTest', scope='module', on_build=test)

def load(ctx: AnnotationRegistry):
    ctx.registerAnot(moduleTest)
    ctx.registerAnot(methodTest)

    ctx.registerAnot(lifecycle.service)
    ctx.registerAnot(lifecycle.indexed)
    ctx.registerAnot(lifecycle.indexedType)
    
    ctx.registerAnot(networking.remote)
    ctx.onPostProcess(networking.post_process)
    ctx.onPostProcess(manifest.post_process)