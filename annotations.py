from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal

if TYPE_CHECKING:
    from dir_scan import BuildProcessCtx

ANNOTATION_PREFIX = '--@'
ARG_SEP = ', '

type retention = Literal['build', 'init', 'runtime']
type scope = Literal['module', 'method', 'type']
type argProcessor = Callable[[str], Any]

@dataclass
class AnnotationBuildCtx():
    build_ctx: BuildProcessCtx
    file: Path
    line: int

#for extensions to define annotations
@dataclass
class AnnotationDef():
    name: str
    args: list[argProcessor]=field(default_factory=list)
    kwargs: dict[str, argProcessor]=field(default_factory=dict)
    retention: retention='init'
    scope: scope='module'
    mutual_include: list[AnnotationDef]=field(default_factory=list)
    mutual_exclude: list[AnnotationDef]=field(default_factory=list)

    def on_build(self, ctx: AnnotationBuildCtx):
        ...

    def check_relationships(self, annotations: list[Annotation]):
        include_checks: list[AnnotationDef] = []
        for anot in annotations:
            assert not anot.adef in self.mutual_exclude
            include_checks.append(anot.adef)

        for anot in self.mutual_include:
            assert anot in include_checks

#an instance of an annotation found when processing
class Annotation():
    def __init__(self, registry: AnnotationRegistry, text: str):
        parts = text.removeprefix(ANNOTATION_PREFIX).split(ARG_SEP)

        self.adef = registry.get(parts[1])
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


class AnnotationRegistry():
    registry: dict[str, AnnotationDef] = {}
    def register(self, annotation: AnnotationDef):
        self.registry[annotation.name] = annotation

    def get(self, name: str):
        return self.registry[name]