from typing import Any, Callable, Literal

ANNOTATION_PREFIX = '--@'
ARG_SEP = ', '

type retention = Literal['build', 'init', 'runtime']
type scope = Literal['module', 'method']

class BuildProcessCtx():
    def __init__(self):
        pass

#for extensions to define annotations
type argProcessor = Callable[[str], Any]
class AnnotationDef():
    def __init__(self, name: str, args: list[argProcessor]=[], kwargs: dict[str, argProcessor]={}, retention: retention='init', scope: scope='module'):
        self.name = name

        self.args = args
        self.kwargs = kwargs
        self.retention = retention
        self.scope = scope

    def on_build(self, ctx: BuildProcessCtx):
        ...

#an instance of an annotation found when processing
class Annotation():
    def __init__(self, definition: AnnotationDef, text: str):
        self.adef = definition

        parts = text.removeprefix(ANNOTATION_PREFIX).split(ARG_SEP)
        self.name = parts[0]

        self.kwargs_val: dict[str, Any] = {}
        self.args_val: list[Any] = []
        self.parse_args(parts[1:-1])

        assert len(self.args_val) == len(self.adef.args), 'missing positional arguments'
        
    def parse_args(self, args: list[str]):
        for i, arg in enumerate(args):
            if '=' in arg:
                name, val = arg.split('=')
                proc = self.adef.kwargs[name]
                self.kwargs_val[name] = proc(val)
            else:
                proc = self.adef.args[i]
                self.args_val[i] = proc(arg)


class ExtensionContext():
    registry: dict[str, AnnotationDef] = []
    def registerAnnotation(self, annotation: AnnotationDef):
        self.registry[annotation.name] = annotation