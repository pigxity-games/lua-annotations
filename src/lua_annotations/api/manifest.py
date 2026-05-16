from dataclasses import dataclass, field
from typing import Any

from lua_annotations.build_process import Environment


@dataclass
class ManifestHooks:
    annotation_handlers: dict[str, Any] = field(default_factory=dict)
    init: list[Any] = field(default_factory=list)
    post_init: list[Any] = field(default_factory=list)

    def merged(self, other: 'ManifestHooks'):
        return ManifestHooks(
            annotation_handlers=self.annotation_handlers | other.annotation_handlers,
            init=self.init + other.init,
            post_init=self.post_init + other.post_init,
        )

    def asdict(self):
        return {
            'annotation_handlers': self.annotation_handlers,
            'init': self.init,
            'post_init': self.post_init,
        }


@dataclass
class ManifestServices:
    entries: dict[str, Any] = field(default_factory=dict)
    load_order: list[str] = field(default_factory=list)

    def asdict(self):
        return {
            'entries': self.entries,
            'load_order': self.load_order,
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
    annotations: list[Any] = field(default_factory=list)
    services: ManifestServices = field(default_factory=ManifestServices)
    remotes: ManifestRemotes = field(default_factory=ManifestRemotes)

    def merged_with_shared(self, shared: 'ManifestData'):
        return ManifestData(
            hooks=self.hooks.merged(shared.hooks),
            annotations=self.annotations + shared.annotations,
            services=self.services,
            remotes=self.remotes,
        )

    def asdict(self):
        return {
            'hooks': self.hooks,
            'annotations': self.annotations,
            'services': self.services,
            'remotes': self.remotes,
        }


@dataclass
class ServiceEntry:
    depends: dict[str, list[str]]
    getAdornee: Any
    kind: str
    tags: list[str] | None = None
    data_service: str | None = None

    def asdict(self):
        out = {
            'depends': self.depends,
            'getAdornee': self.getAdornee,
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
