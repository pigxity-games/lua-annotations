from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any

from lua_annotations.api.lua_dict import LuaPath
from lua_annotations.build_process import Environment


def merge_dicts(target: dict[Any, Any], added: dict[Any, Any]):
    for key, value in added.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merge_dicts(current, value)
        else:
            target[key] = value


@dataclass
class ManifestMethodRef:
    module: str
    method: str

    def asdict(self):
        return {
            'module': self.module,
            'method': self.method,
        }


@dataclass
class ManifestHooks:
    annotation_handlers: dict[str, Any] = field(default_factory=dict)
    pre_init: list[Any] = field(default_factory=list)
    module_handlers: list[Any] = field(default_factory=list)
    post_init: list[Any] = field(default_factory=list)

    def merged(self, other: 'ManifestHooks'):
        return ManifestHooks(
            annotation_handlers=self.annotation_handlers | other.annotation_handlers,
            pre_init=self.pre_init + other.pre_init,
            module_handlers=self.module_handlers + other.module_handlers,
            post_init=self.post_init + other.post_init,
        )

    def asdict(self):
        return {
            'pre_init': self.pre_init,
            'annotation_handlers': self.annotation_handlers,
            'module_handlers': self.module_handlers,
            'post_init': self.post_init,
        }


@dataclass
class ManifestAnnotation:
    name: str
    args: list[Any]
    kwargs: dict[str, Any]
    data: dict[Any, Any] = field(default_factory=dict)

    def asdict(self):
        return {
            'name': self.name,
            'args': self.args,
            'kwargs': self.kwargs,
            'data': self.data,
        }


@dataclass
class ManifestModule:
    path: LuaPath
    annotations: dict[str, ManifestAnnotation] = field(default_factory=dict)
    data: dict[Any, Any] = field(default_factory=dict)

    def merged(self, other: 'ManifestModule'):
        data = dict(self.data)
        merge_dicts(data, other.data)
        return ManifestModule(
            path=other.path,
            annotations=self.annotations | other.annotations,
            data=data,
        )

    def asdict(self):
        return {
            'annotations': self.annotations,
            'data': self.data,
        }


@dataclass
class ManifestData:
    hooks: ManifestHooks = field(default_factory=ManifestHooks)
    modules: dict[str, ManifestModule] = field(default_factory=dict)
    load_order: list[str] = field(default_factory=list)

    def merged_with_shared(self, shared: 'ManifestData'):
        modules = dict(shared.modules)
        for name, module in self.modules.items():
            current = modules.get(name)
            modules[name] = current.merged(module) if current else module

        return ManifestData(
            hooks=self.hooks.merged(shared.hooks),
            modules=modules,
            load_order=shared.load_order + self.load_order,
        )

    def asdict(self):
        return {
            'hooks': self.hooks,
            'modules': self.modules,
            'load_order': self.load_order,
        }


@dataclass
class ServiceData:
    depends: dict[str, list[str]]
    kind: str
    tags: list[str] | None = None
    data_service: str | None = None

    def asdict(self):
        out = {
            'depends': self.depends,
            'kind': self.kind,
        }

        if self.tags is not None:
            out['tags'] = self.tags

        if self.data_service is not None:
            out['data_service'] = self.data_service

        return out


@dataclass
class ManifestMethod:
    path: LuaPath
    method: str

    @classmethod
    def from_path(cls, path: PurePath | LuaPath, method: str):
        if isinstance(path, LuaPath):
            return cls(path, method)

        return cls(LuaPath(path, require=True, cache=True), method)


type ManifestMap = dict[Environment, ManifestData]
