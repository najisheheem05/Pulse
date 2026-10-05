"""Impact graph: hospital.yaml -> networkx DiGraph, traversal to services at risk."""
from __future__ import annotations
import yaml
import networkx as nx


def load_model(path: str = "data/hospital.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def build_graph(model: dict) -> nx.DiGraph:
    g = nx.DiGraph()
    for ep, meta in (model.get("endpoints", {}) or {}).items():
        g.add_node(ep, kind="endpoint", **(meta or {}))
        for app in (meta or {}).get("apps", []):
            g.add_node(app, kind="application")
            g.add_edge(ep, app, rel="runs")
    for app, meta in (model.get("applications", {}) or {}).items():
        if not g.has_node(app):
            g.add_node(app, kind="application")
        for svc in (meta or {}).get("serves", []):
            if not g.has_node(svc):
                sdef = (model.get("services", {}) or {}).get(svc, {})
                g.add_node(svc, kind="service", **sdef)
            g.add_edge(app, svc, rel="serves")
    for svc, meta in (model.get("services", {}) or {}).items():
        if not g.has_node(svc):
            g.add_node(svc, kind="service", **(meta or {}))
    return g


def paths_to_services(g: nx.DiGraph, endpoint_id: str) -> list[tuple[str, list[str]]]:
    """All endpoint -> app -> service paths."""
    out = []
    if not g.has_node(endpoint_id):
        return out
    for node in g.nodes:
        if g.nodes[node].get("kind") == "service":
            try:
                for p in nx.all_simple_paths(g, endpoint_id, node, cutoff=3):
                    out.append((node, p))
            except nx.NetworkXNoPath:
                continue
    return out


def lateral_reachable_services(g: nx.DiGraph, model: dict, endpoint_id: str) -> list[str]:
    """Services reachable via segment pivot (potential, exposure 0.3)."""
    eps = model.get("endpoints", {}) or {}
    segs = model.get("segments", {}) or {}
    src_seg = (eps.get(endpoint_id, {}) or {}).get("segment", "")
    reaches = set((segs.get(src_seg, {}) or {}).get("reaches", []))
    svcs: set[str] = set()
    apps = model.get("applications", {}) or {}
    for ep2, meta in eps.items():
        if ep2 == endpoint_id:
            continue
        if (meta or {}).get("segment") in reaches:
            # shares reachability: lateral candidate
            for app in (meta or {}).get("apps", []):
                for s in (apps.get(app, {}) or {}).get("serves", []):
                    svcs.add(s)
    return sorted(svcs)


def graph_json(g: nx.DiGraph, highlight: dict[str, list[str]] | None = None) -> dict:
    highlight = highlight or {}
    nodes, edges = [], []
    hot: set[str] = set()
    for paths in highlight.values():
        for p in paths:
            hot.update(p)
    for n, attr in g.nodes(data=True):
        nodes.append({"id": n, "kind": attr.get("kind", "?"),
                      "tier": (attr.get("tier") if attr.get("kind") == "service" else None),
                      "hot": n in hot})
    for u, v, attr in g.edges(data=True):
        edges.append({"source": u, "target": v,
                      "hot": (u in hot and v in hot)})
    return {"nodes": nodes, "edges": edges}
