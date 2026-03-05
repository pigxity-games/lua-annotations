from dataclasses import dataclass, field, fields, replace
from graphlib import TopologicalSorter
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional

ENVIRONMENTS = ('client', 'server', 'shared')

if TYPE_CHECKING:
    from lua_annotations.build_process import BuildProcessCtx, PostProcessCtx
    from lua_annotations.parser_schemas import Annotation
    from parser import FileParser

ARG_SEP = ', '

type retention = Literal['build', 'init', 'runtime']
type scope = Literal['module', 'method', 'type', 'returned_value']
type argProcessor = Callable[[str], Any]


@dataclass
class AnnotationBuildCtx:
    annotation: 'Annotation'
    parser: 'FileParser'
    build_ctx: 'BuildProcessCtx'


type OnBuild = Callable[[AnnotationBuildCtx], None]


def merge(parent: Any, value: Any):
    if isinstance(parent, dict):
        return parent | value
    if isinstance(parent, (list, tuple)):
        return parent + value
    return value


# for extensions to define annotations
@dataclass
class AnnotationDef:
    """An annotation definition; all Annotation classes are attached to one of these."""

    name: str
    args: list[argProcessor] = field(default_factory=list)
    kwargs: dict[str, argProcessor] = field(default_factory=dict)
    retention: retention = 'build'
    scope: scope = 'module'
    mutual_include: list['AnnotationDef'] = field(default_factory=list)
    mutual_exclude: list['AnnotationDef'] = field(default_factory=list)
    on_build: Optional[OnBuild] = None
    extends: Optional[AnnotationDef] = None

    def extend(self, other: AnnotationDef):
        updates = {}
        for f in fields(type(self)):
            updates[f.name] = merge(getattr(self, f.name), getattr(other, f.name))

        other.extends = self
        return replace(other, **updates)


@dataclass
class FileBuildCtx:
    build_ctx: 'BuildProcessCtx'
    parser: 'FileParser'
    filepath: Path


type FileBuildHook = Callable[[FileBuildCtx], None]
type PostBuildHook = Callable[[PostProcessCtx], None]


class Extension:
    hook_order: Literal['before', 'after'] = 'after'

    def on_post_process(self, ctx: PostProcessCtx): ...
    def on_file_process(self, ctx: FileBuildCtx): ...
    def load(self, ctx: ExtensionRegistry): ...


@dataclass
class SortedRegistry:
    """Topologically sorted file_build_hooks and post_build_hooks"""

    file_build_hooks: list[FileBuildHook]
    post_build_hooks: list[PostBuildHook]
    anot_registry: dict[str, AnnotationDef]


class ExtensionRegistry:
    """Provides an API to register and get extensions"""

    def __init__(self):
        self.anot_registry: dict[str, AnnotationDef] = {}
        self.extensions: dict[str, Extension] = {}
        self.ext_graph: dict[str, list[str]] = {}
        self.ext_load_order: list[str] = []

    def register_extension(
        self,
        extension: Extension,
        deps: list[str] = [],
        hook_order: Literal['before', 'after'] = 'after',
    ):
        name = type(extension).__name__
        extension.hook_order = hook_order
        self.extensions[name] = extension
        self.ext_graph[name] = deps

    def register_anot(self, anot: AnnotationDef):
        self.anot_registry[anot.name] = anot

    def sort_extensions(self):
        ext_layers = [[self.extensions[ext] for ext in layer] for layer in topo_layers(self.ext_graph)]
        load_exts = [x for y in ext_layers for x in y]
        hook_exts = [x for y in shift_exts(ext_layers) for x in y]

        for ext in load_exts:
            ext.load(self)

        return SortedRegistry(
            [ext.on_file_process for ext in hook_exts],
            [ext.on_post_process for ext in hook_exts],
            self.anot_registry,
        )


def shift_exts(layers: list[list[Extension]], flag: str = 'before'):
    befores = []
    for layer in layers:
        befores += [e for e in layer if e.hook_order == flag]
        layer[:] = [e for e in layer if e.hook_order != flag]

    if befores:
        layers[0][:0] = befores

    return layers


def topo_layers(graph: dict[str, list[str]]):
    ts = TopologicalSorter(graph)
    ts.prepare()

    layers: list[list[str]] = []
    while ts.is_active():
        ready = list(ts.get_ready())
        ready.sort()
        layers.append(list(ready))
        ts.done(*ready)
    return layers
