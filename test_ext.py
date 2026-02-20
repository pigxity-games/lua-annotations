from api.annotations import AnnotationBuildCtx, AnnotationDef, ExtensionRegistry


def test(ctx: AnnotationBuildCtx):
    print(f'Hello World, {ctx.annotation.name}!')


def load(ctx: ExtensionRegistry):
    ctx.register_anot(
        AnnotationDef(
            'methodTest',
            scope='method',
            args=[str],
            kwargs={'testKwarg': str},
            on_build=test,
        )
    )
    ctx.register_anot(AnnotationDef('moduleTest', scope='module', on_build=test))
    ctx.register_anot(AnnotationDef('typeTest', scope='type', on_build=test))