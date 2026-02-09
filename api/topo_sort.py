# code found online

from collections import defaultdict, deque
from typing import Any, Iterable

def topo_sort(deps: dict[str, Iterable[str]]) -> list[str]:
    """
    deps maps: node -> its dependencies (must come before node)

    Returns a topological order (dependencies first).
    Raises ValueError if a cycle exists.
    """
    # Collect all nodes (including ones that appear only as dependencies)
    nodes = set(deps.keys())
    for _, ds in deps.items():
        for d in ds:
            nodes.add(d)

    # Build adjacency list: dependency -> list of dependents
    adj: dict[Any, list[Any]] = defaultdict(list)  # dep -> [things that depend on dep]
    indeg = {n: 0 for n in nodes}

    for node, ds in deps.items():
        for dep in ds:
            adj[dep].append(node)
            indeg[node] += 1

    # Start with nodes that have no dependencies
    q = deque([n for n in nodes if indeg[n] == 0])

    order: list[str] = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in adj.get(u, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)

    if len(order) != len(nodes):
        # Nodes not output are part of (or reachable from) a cycle
        cyclic = [n for n in nodes if indeg[n] > 0]
        raise ValueError(f"Cycle detected among: {cyclic}")

    return order