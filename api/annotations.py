from dataclasses import dataclass, field
from graphlib import TopologicalSorter
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
    def load(self, ctx: ExtensionRegistry):
        ...


@dataclass
class SortedRegistry():
    """Topologically sorted file_build_hooks and post_build_hooks"""
    file_build_hooks: list[FileBuildHook]
    post_build_hooks: list[PostBuildHook]
    anot_registry: dict[str, AnnotationDef]

class ExtensionRegistry():
    """Provides an API to register and get extensions"""

    def __init__(self):
        self.anot_registry: dict[str, AnnotationDef] = {}
        self.extensions: dict[str, Extension] = {}
        self.ext_graph: dict[str, list[str]] = {}
        self.ext_load_order: list[str] = []


    def register_extension(self, extension: Extension, deps: list[str] = []):
        name = type(extension).__name__
        self.extensions[name] = extension
        self.ext_graph[name] = deps

    
    def register_anot(self, anot: AnnotationDef):
        self.anot_registry[anot.name] = anot


    def sort_extensions(self):
        ts = TopologicalSorter(self.ext_graph)
        exts = [self.extensions[ext] for ext in ts.static_order()]

        #register annotations
        for ext in exts:
            ext.load(self)

        return SortedRegistry(
            [ext.on_file_process for ext in exts],
            [ext.on_post_process for ext in exts],
            self.anot_registry
        )