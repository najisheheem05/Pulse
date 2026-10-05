"""Generate panel visuals: scoring chart + topology graph. Run: python3 scripts/make_visuals.py"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# 1. Scoring comparison chart (measured values from live demo)
scenarios = ["D\nbenign\npatching", "A\nradiology\nws → T2", "C\ninfusion\npump → T1", "B\npharmacy\nsrv → T1"]
scores = [0.0, 31.0, 38.8, 40.6]
colors = ["#4ade80", "#ffb84d", "#ff5c5c", "#ff2222"]
tiers = ["—", "T2 imaging\n120-min clock", "T1 medication\n15-min clock\npassive-only", "T1 medication\n15-min clock"]

fig, ax = plt.subplots(figsize=(9, 4.2))
bars = ax.bar(scenarios, scores, color=colors, edgecolor="white", linewidth=1.2)
ax.set_ylabel("Incident risk score (0–100)", fontsize=10)
ax.set_title("Same attack behavior, very different clinical rank  —  R1+R2+R3 on workstation vs Tier-1 server", fontsize=11, pad=12)
ax.set_ylim(0, 50)
for b, s, t in zip(bars, scores, tiers):
    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.8, f"{s}", ha="center", fontsize=12, fontweight="bold")
    ax.text(b.get_x() + b.get_width()/2, 2, t, ha="center", fontsize=8, color="white" if s > 15 else "#333")
fig.tight_layout()
fig.savefig("docs/screenshots/scoring_comparison.png", dpi=150, facecolor="white")
print("wrote docs/screenshots/scoring_comparison.png")

# 2. Topology: endpoint -> app -> service
import networkx as nx
import yaml
with open("data/hospital.yaml") as f:
    model = yaml.safe_load(f)
g = nx.DiGraph()
for ep, meta in model["endpoints"].items():
    g.add_node(ep, kind="endpoint")
    for app in meta.get("apps", []):
        g.add_node(app, kind="app")
        g.add_edge(ep, app)
for app, meta in model["applications"].items():
    for svc in meta.get("serves", []):
        g.add_node(svc, kind="service")
        g.add_edge(app, svc)

hot = {"rad-ws-02", "pacs_viewer", "pacs", "imaging_reads",
       "pharm-srv-01", "pharmacy", "medication_administration",
       "pump-icu-04", "infusion_mgmt"}
fig2, ax2 = plt.subplots(figsize=(12, 7))
pos = nx.spring_layout(g, seed=7, k=0.9)
node_colors = []
for n in g.nodes:
    k = {"endpoint": "#60a5fa", "app": "#c084fc", "service": "#4ade80"}.get(g.nodes[n].get("kind", "endpoint"), "#999")
    if n in hot:
        k = "#ff5c5c"
    node_colors.append(k)
nx.draw_networkx_nodes(g, pos, node_color=node_colors, node_size=700, ax=ax2, edgecolors="white")
nx.draw_networkx_edges(g, pos, arrows=True, arrowsize=10, edge_color="#94a3b8", width=1.0, ax=ax2,
                       connectionstyle="arc3,rad=0.05")
nx.draw_networkx_labels(g, pos, font_size=7, ax=ax2)
ax2.set_title("Hospital dependency graph — red = nodes on live attack paths (A: radiology, B: pharmacy, C: pump)", fontsize=11)
ax2.axis("off")
fig2.tight_layout()
fig2.savefig("docs/screenshots/topology.png", dpi=150, facecolor="white")
print("wrote docs/screenshots/topology.png")

# 3. Noisy-OR confidence illustration
fig3, ax3 = plt.subplots(figsize=(7, 3.5))
rules = ["R1\n0.60", "R1+R2\n0.92", "R1+R2+R3\n0.976", "R1+R2+R3+R5\n0.989"]
conf = [0.60, 0.92, 0.976, 0.989]
ax3.bar(rules, conf, color=["#94a3b8", "#60a5fa", "#c084fc", "#ff5c5c"], edgecolor="white")
ax3.set_ylim(0, 1.1)
ax3.set_ylabel("Noisy-OR confidence")
ax3.set_title("Correlator: stacked weak signals → high confidence  (1 − Π(1−w))", fontsize=11)
for x, y in zip(rules, conf):
    ax3.text(x, y + 0.02, f"{y:.3f}", ha="center", fontweight="bold")
fig3.tight_layout()
fig3.savefig("docs/screenshots/noisy_or.png", dpi=150, facecolor="white")
print("wrote docs/screenshots/noisy_or.png")
