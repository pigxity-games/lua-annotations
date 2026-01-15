from typing import Any, Generic, Literal, Optional, TypeVar

ANNOTATION_PREFIX = '--@'
ARG_SEP = ', '

type retention = Literal['build', 'init', 'runtime']
type scope = Literal['module', 'method']

class BuildProcessCtx():
    def __init__(self):
        pass

T = TypeVar('T')
class ArgumentParser(Generic[T]):
    def __init__(self, positional: bool=True, name: Optional[str]=None):
        self.positional = positional
        self.name = name

    def process(self, value: str) -> T:
        ...

#for extensions to define annotations
class AnnotationDef():
    def __init__(self, name: str, args: list[ArgumentParser[Any]]=[], retention: retention='init', scope: scope='module'):
        self.name = name

        self.args = args
        self.retention = retention
        self.scope = scope

    def build_process(self, ctx: BuildProcessCtx):
        ...

#an instance of an annotation found when processing
class Annotation():
    def __init__(self, definition: AnnotationDef, text: str):
        self.definition = definition

        parts = text.removeprefix(ANNOTATION_PREFIX).split(ARG_SEP)
        self.name = parts[0]
        self.arg_values = parts[1:-1]

    def process_args(self):
        results: list[Any] = []
        for processor, value in zip(self.definition.args, self.arg_values):
            results.append(processor.process(value))

        return results


class ExtensionContext():
    registry: list[AnnotationDef] = []
    def registerAnnotation(self, annotation: AnnotationDef):
        self.registry.append(annotation)