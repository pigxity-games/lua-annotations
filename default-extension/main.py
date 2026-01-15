from annotation_parser import AnnotationDef, ArgumentParser, ExtensionContext

class TestArg(ArgumentParser[str]):
    def process(self, value: str) -> str:
        print(value)
        return value

methodTest = AnnotationDef('methodTest', scope='method', args=[
    TestArg()
])

def load(ctx: ExtensionContext):
    ctx.registerAnnotation(methodTest)