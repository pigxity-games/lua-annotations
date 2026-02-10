from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional

ENVIRONMENTS = ('client', 'server', 'shared')

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
    """An annotation definition; all Annotation classes are attached to one of these."""
    name: str
    args: list[argProcessor]=field(default_factory=list)
    kwargs: dict[str, argProcessor]=field(default_factory=dict)
    retention: retention='build'
    scope: scope='module'
    mutual_include: list['AnnotationDef']=field(default_factory=list)
    mutual_exclude: list['AnnotationDef']=field(default_factory=list)
    on_build: Optional[OnBuild]=None
    extends: list['AnnotationDef']=field(default_factory=list)
    

@dataclass
class FileBuildCtx():
    build_ctx: 'BuildProcessCtx'
    parser: 'FileParser'
    filepath: Path

type FileBuildHook = Callable[[FileBuildCtx], None]
type PostBuildHook =  Callable[[PostProcessCtx], None]

class Extension():
    def on_post_process(self, ctx: PostProcessCtx):
        ...
    def on_file_process(self, ctx: FileBuildCtx):
        ...
    def load(self, ctx: AnnotationRegistry):
        ...

@dataclass
class AnnotationRegistry():
    """Provides an API for extensions to register annotations"""
    registry: dict[str, AnnotationDef] = field(default_factory=dict)
    file_build_hooks: list[FileBuildHook]=field(default_factory=list)
    post_build_hooks: list[PostBuildHook]=field(default_factory=list)

    def registerAnot(self, annotation: AnnotationDef, name: Optional[str]=None):
        self.registry[name or annotation.name] = annotation

    def registerExtension(self, extension: Extension):
        extension.load(self)
        self.onPostProcess(extension.on_post_process)
        self.onFileProcess(extension.on_file_process)

    def onFileProcess(self, hook: FileBuildHook):
        self.file_build_hooks.append(hook)

    def onPostProcess(self, hook: PostBuildHook):
        self.post_build_hooks.append(hook)
