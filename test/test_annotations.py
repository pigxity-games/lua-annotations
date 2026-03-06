from types import SimpleNamespace

from lua_annotations.api.annotations import ExtensionRegistry
from lua_annotations.extensions import default as default_ext
from lua_annotations.extensions.game_framework import main as game_framework_ext
from lua_annotations.extensions.game_framework.lifecycle import get_runtime_load_order


def test_service_annotation_keeps_dependency_parent():
    reg = ExtensionRegistry()
    default_ext.load(reg)
    game_framework_ext.load(reg)

    sorted_reg = reg.sort_extensions()
    service = sorted_reg.anot_registry['service']

    assert service.extends is not None
    assert service.extends.name == 'dependency'


def make_service_anot(name: str, kind: str, kwargs: dict[str, list[str]]):
    return SimpleNamespace(
        name=kind,
        kwargs_val=kwargs,
        adornee=SimpleNamespace(returned_name=name),
    )


def test_runtime_load_order_keeps_depends_and_load_after_edges():
    services = [
        make_service_anot('MainService', 'service', {'depends': ['DataService'], 'load_after': ['LoggerService']}),
        make_service_anot('DataService', 'service', {}),
        make_service_anot('LoggerService', 'service', {}),
    ]

    load_order = get_runtime_load_order(services)

    assert load_order.index('DataService') < load_order.index('MainService')
    assert load_order.index('LoggerService') < load_order.index('MainService')


def test_runtime_load_order_excludes_dependency_nodes():
    services = [
        make_service_anot('CounterRegistry', 'dependency', {'load_after': ['Counter']}),
        make_service_anot('Counter', 'component', {'depends': ['CounterRegistry']}),
    ]

    load_order = get_runtime_load_order(services)

    assert load_order == ['Counter']
