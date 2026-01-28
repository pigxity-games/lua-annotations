from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional

if TYPE_CHECKING:
    from dir_scan import BuildProcessCtx
    from parser_schemas import Annotation, Adornee
    from parser import FileParser

ARG_SEP = ', '

type retention = Literal['build', 'init', 'runtime']
type scope = Literal['module', 'method', 'type']
type argProcessor = Callable[[str], Any]

@dataclass
class AnnotationBuildCtx():
    build_ctx: BuildProcessCtx
    annotation: Annotation
    adornee: Adornee
    parser: FileParser
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

type FileBuildHook = Callable[[AnnotationBuildCtx], None]
type PostBuildHook =  Callable[[BuildProcessCtx], None]
class AnnotationRegistry():
    registry: dict[str, AnnotationDef] = {}
    file_build_hooks: list[FileBuildHook]=[]
    post_build_hooks: list[PostBuildHook]=[]

    def registerAnot(self, annotation: AnnotationDef, name: Optional[str]=None):
        self.registry[name or annotation.name] = annotation

    def onFileProcess(self, hook: FileBuildHook):
        self.file_build_hooks.append(hook)

    def onPostProcess(self, hook: PostBuildHook):
        self.post_build_hooks.append(hook)