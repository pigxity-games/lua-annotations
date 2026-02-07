from annotations import AnnotationBuildCtx, AnnotationDef, AnnotationRegistry


def test(ctx: AnnotationBuildCtx):
    print(f'Hello World, {ctx.annotation.name}!')


def load(ctx: AnnotationRegistry):
    ctx.registerAnot(
        AnnotationDef(
            'methodTest',
            scope='method',
            args=[str],
            kwargs={'testKwarg': str},
            on_build=test,
        )
    )
    ctx.registerAnot(AnnotationDef('moduleTest', scope='module', on_build=test))
    ctx.registerAnot(AnnotationDef('typeTest', scope='type', on_build=test))
