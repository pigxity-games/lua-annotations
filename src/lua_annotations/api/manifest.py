from dataclasses import dataclass, field
from typing import Any, Literal

from lua_annotations.build_process import Environment


type HookPhase = Literal['pre_init', 'module_handlers', 'post_init']


def normalize_manifest_value(value: Any):
    if value is None:
        return None

    asdict = getattr(value, 'asdict', None)
    if callable(asdict):
        return asdict()

    return value


def merge_manifest_value(current: Any, added: Any):
    current = normalize_manifest_value(current)
    added = normalize_manifest_value(added)

    if current is None:
        return added

    if added is None:
        return current

    if isinstance(current, dict) and isinstance(added, dict):
        merged = dict(current)
        for key, value in added.items():
            merged[key] = merge_manifest_value(merged.get(key), value)
        return merged

    if isinstance(current, list) and isinstance(added, list):
        return current + added

    return added


@dataclass
class ManifestHook:
    module: str
    method: str
    module_path: Any = field(repr=False, compare=False)

    def asdict(self):
        return {
            'module': self.module,
            'method': self.method,
        }

    def register_module_path(self, resolver: Any):
        self.module_path.to_lua(resolver)


@dataclass
class ManifestHooks:
    pre_init: list[ManifestHook] = field(default_factory=list)
    module_handlers: list[ManifestHook] = field(default_factory=list)
    post_init: list[ManifestHook] = field(default_factory=list)
    annotation_handlers: dict[str, ManifestHook] = field(default_factory=dict)

    def merged(self, other: 'ManifestHooks'):
        return ManifestHooks(
            pre_init=self.pre_init + other.pre_init,
            module_handlers=self.module_handlers + other.module_handlers,
            post_init=self.post_init + other.post_init,
            annotation_handlers=self.annotation_handlers | other.annotation_handlers,
        )

    def register_module_paths(self, resolver: Any):
        for hook in self.pre_init:
            hook.register_module_path(resolver)

        for hook in self.module_handlers:
            hook.register_module_path(resolver)

        for hook in self.post_init:
            hook.register_module_path(resolver)

        for hook in self.annotation_handlers.values():
            hook.register_module_path(resolver)

    def asdict(self):
        return {
            'pre_init': self.pre_init,
            'annotation_handlers': self.annotation_handlers,
            'module_handlers': self.module_handlers,
            'post_init': self.post_init,
        }


@dataclass
class ManifestModuleEntry:
    module_path: Any = field(repr=False, compare=False)
    annotations: dict[str, list[Any]] = field(default_factory=dict)
    data: Any = None

    def merged(self, other: 'ManifestModuleEntry'):
        merged_annotations = {
            key: list(vals)
            for key, vals in other.annotations.items()
        }

        for key, vals in self.annotations.items():
            merged_annotations.setdefault(key, [])
            merged_annotations[key].extend(vals)

        return ManifestModuleEntry(
            module_path=self.module_path,
            annotations=merged_annotations,
            data=merge_manifest_value(other.data, self.data),
        )

    def register_module_path(self, resolver: Any):
        self.module_path.to_lua(resolver)

    def asdict(self):
        return {
            'annotations': self.annotations,
            'data': self.data,
        }


@dataclass
class ManifestRemotes:
    client: dict[str, dict[str, Any]] = field(default_factory=dict)
    server: dict[str, dict[str, Any]] = field(default_factory=dict)

    def asdict(self):
        return {
            'client': self.client,
            'server': self.server,
        }


@dataclass
class ManifestData:
    hooks: ManifestHooks = field(default_factory=ManifestHooks)
    modules: dict[str, ManifestModuleEntry] = field(default_factory=dict)
    load_order: list[str] = field(default_factory=list)
    remotes: ManifestRemotes = field(default_factory=ManifestRemotes)

    def merged_with_shared(self, shared: 'ManifestData'):
        merged_modules = {name: entry for name, entry in shared.modules.items()}

        for name, entry in self.modules.items():
            shared_entry = merged_modules.get(name)
            if shared_entry is None:
                merged_modules[name] = entry
            else:
                merged_modules[name] = entry.merged(shared_entry)

        return ManifestData(
            hooks=self.hooks.merged(shared.hooks),
            modules=merged_modules,
            load_order=list(self.load_order if self.load_order else shared.load_order),
            remotes=self.remotes,
        )

    def register_module_paths(self, resolver: Any):
        self.hooks.register_module_paths(resolver)

        for entry in self.modules.values():
            entry.register_module_path(resolver)

    def asdict(self):
        return {
            'hooks': self.hooks,
            'modules': self.modules,
            'load_order': self.load_order,
            'remotes': self.remotes,
        }


@dataclass
class ServiceEntry:
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
class RemoteEntry:
    service: str
    method: str
    remoteType: str
    middleware: list[str] = field(default_factory=list)

    def asdict(self):
        return {
            'service': self.service,
            'method': self.method,
            'remoteType': self.remoteType,
            'middleware': self.middleware,
        }


type ManifestMap = dict[Environment, ManifestData]
