from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional

if TYPE_CHECKING:
    from build_process import BuildProcessCtx, PostProcessCtx
    from parser_schemas import Annotation
    from parser import FileParser

ARG_SEP = ', '

type retention = Literal['build', 'init', 'runtime']
type scope = Literal['module', 'method', 'type']
type argProcessor = Callable[[str], Any]

@dataclass
class AnnotationBuildCtx():
    annotation: 'Annotation'
    parser: 'FileParser'
    build_ctx: 'BuildProcessCtx'

type OnBuild = Callable[[AnnotationBuildCtx], None]

#for extensions to define annotations
@dataclass
class AnnotationDef():
    name: str
    args: list[argProcessor]=field(default_factory=list)
    kwargs: dict[str, argProcessor]=field(default_factory=dict)
    retention: retention='init'
    scope: scope='module'
    mutual_include: list['AnnotationDef']=field(default_factory=list)
    mutual_exclude: list['AnnotationDef']=field(default_factory=list)
    on_build: Optional[OnBuild]=None

@dataclass
class FileBuildCtx():
    build_ctx: 'BuildProcessCtx'
    parser: 'FileParser'
    filepath: Path

type FileBuildHook = Callable[[FileBuildCtx], None]
type PostBuildHook =  Callable[[PostProcessCtx], None]

@dataclass
class AnnotationRegistry():
    registry: dict[str, AnnotationDef] = field(default_factory=dict)
    file_build_hooks: list[FileBuildHook]=field(default_factory=list)
    post_build_hooks: list[PostBuildHook]=field(default_factory=list)

    def registerAnot(self, annotation: AnnotationDef, name: Optional[str]=None):
        self.registry[name or annotation.name] = annotation

    def onFileProcess(self, hook: FileBuildHook):
        self.file_build_hooks.append(hook)

    def onPostProcess(self, hook: PostBuildHook):
        self.post_build_hooks.append(hook)
