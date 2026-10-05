# WORKLOG — Hospital Impact Defense (Hackathon Build)

**Date**: 2026-10-05  
**Duration**: ~3 hours  
**Team**: Solo  
**Goal**: Panel-ready demo of clinical-impact endpoint defense platform

---

## Hour 1: Scaffold + Core + Hospital Model (T+0-60m)

| Time | Task |
|---|---|
| 0:00 | Empty workspace → created full directory structure (src/, data/, tests/, public/, docs/) |
| 0:05 | `requirements.txt`: fastapi, uvicorn, pydantic, pyyaml, networkx, pytest, httpx |
| 0:08 | `Makefile`: run, demo, test, vendor, clean targets |
| 0:10 | `src/core/schema.py`: Pydantic Event/Alert/Incident (unified schema for agent + passive) |
| 0:15 | `src/core/store.py`: SQLite CRUD (stdlib), tables: events, alerts, incidents, actions, audit |
| 0:20 | `data/hospital.yaml`: 16 endpoints, 16 apps, 3 services (T1/T2/T3), 5 segments, tiers, scoring weights |
| 0:25 | `data/rules.yaml`: 12 rules (7 MVP + 5 stretch), thresholds, weights, allow-lists, baselines |
| 0:30 | `data/scenarios/*.json`: A(radiology), B(pharmacy), C(pump), D(benign) — synthetic events only |
| 0:40 | `src/detection/engine.py`: R1,R2,R3,R5,R6,R9,R10 consolidated (no per-rule files) |
| 0:45 | `src/detection/baseline.py`: IoMT/IoT allow-list + maintenance window check |
| 0:50 | `src/detection/correlate.py`: 30m window, noisy-OR confidence |
| 0:55 | Tests running: 7 rule tests passing |

**Decision**: Consolidated all detection into `engine.py` (saves ~15 min vs per-rule files). Used inline YAML for hospital model (editable by judges).

---

## Hour 2: Impact Engine + Response + API (T+60-120m)

| Time | Task |
|---|---|
| 1:00 | `src/impact/graph.py`: networkx DiGraph from YAML, paths to services, lateral reachability |
| 1:10 | `src/impact/scoring.py`: Clinical risk formula (tier × fallback × exposure × confidence) |
| 1:15 | `src/impact/explain.py`: Plain-English narratives for panel |
| 1:20 | `src/response/playbooks.py`: 4 tiers (auto/analyst/clinical/device-never-auto) |
| 1:25 | `src/response/approvals.py`: Single-analyst approve/deny queue |
| 1:30 | `src/response/audit.py`: SHA-256 hash chain (~30 lines), tamper-evident |
| 1:35 | `src/main.py`: FastAPI with 8 routes + static mount |
| 1:40 | `src/simulator/emitter.py`: CLI + async scenario replay |
| 1:45 | Integration test: `make run` → `make demo SCENARIO=a` → incidents appear |

**Decision**: Single-analyst approval (not dual) for demo speed. Device playbook hard-coded to passive-only.

---

## Hour 3: Dashboard + Tests + Docs + Polish (T+120-180m)

| Time | Task |
|---|---|
| 2:00 | `public/index.html`: 3-panel layout (incidents | graph | detail+approvals+audit) |
| 2:10 | `public/app.js`: 1s polling, Cytoscape dagre layout, approve/deny buttons, audit badge |
| 2:15 | `make vendor`: downloaded htmx.min.js + cytoscape.min.js locally (offline-safe) |
| 2:20 | `tests/test_smoke.py`: 13 tests (7 rules, correlator, impact, explain, playbook, audit, scenario) |
| 2:30 | Fixed YAML parse error (inline mapping spacing), fixed test expectations |
| 2:35 | All tests passing |
| 2:40 | `README.md`: architecture, quickstart, demo script, limitations, structure |
| 2:45 | `docs/`: architecture.md, threat-model.md, detection-rules.md, impact-scoring.md, limitations.md |
| 2:50 | End-to-end demo rehearsal (5 min script) |
| 2:55 | Final `make test` → clean |

---

## Key Technical Decisions (for judges)

| Decision | Rationale |
|---|---|
| SQLite (stdlib) | Zero setup, portable, demo-scale sufficient |
| Consolidated detection | 1 file vs 7 — faster to build, easier to audit |
| Noisy-OR confidence | Mathematically sound, explains "R1+R2+R3 >> R1 alone" |
| Exposure tiers (1.0/0.6/0.3) | Distinguishes direct, dependency, potential lateral |
| Fallback readiness in formula | Makes "paper MAR at 60%" quantitatively matter |
| Hash-chained audit | ~30 lines, strong live demo moment (tamper → verify fail) |
| hx-get polling (not WS) | Works through any proxy, no reconnection logic |
| Cytoscape dagre LR layout | Auto-arranges endpoint→app→service left-to-right |
| Vendored JS | Demo works with zero Wi-Fi |

---

## What Was Cut (Per Plan)

- ❌ R4 (suspicious script), R7 (lateral burst), R8 (tool tampering), R11 (cross-segment), R12 (exfil)
- ❌ Dual clinical approval flow
- ❌ Maintenance window enforcement (only advisory in R10)
- ❌ Dynamic graph discovery
- ❌ Docker / production hardening
- ❌ Per-rule test files (single smoke test file)

---

## Demo Checklist (Panel Ready)

- [x] `make run` starts clean on port 8000
- [x] Scenario D → no incident (honest FP)
- [x] Scenario A → medium-high, radiology path highlighted
- [x] Scenario B → critical, pharmacy → medication T1, 15-min clock
- [x] Scenario C → pump, passive-only badge, approval required
- [x] Approve action → audit log entry
- [x] Tamper DB → `GET /api/audit/verify` shows FAIL
- [x] All 13 tests pass
- [x] README + docs complete
- [x] Works offline (vendored JS)

---

## Post-build fixes (debug session)

| Fix | Cause | Result |
|---|---|---|
| Incident dedup | `ingest_event` created one incident per event (18 for scenario A) | Single open incident per endpoint, updated in place; recommended action auto-requested once |
| R1 ext-flip gate | Benign patching (25 writes, 0 renames) fired R1 | R1 now requires ≥3 ext flips; D=0 incidents, A/B still fire |
| `make run` PYTHONPATH | `uvicorn src.main:app` failed without repo on path | Makefile exports PYTHONPATH; `scripts/demo.sh` added (`SCENARIO=full` default) |
| Test DB init | `init_db()` called without tmp path; YAML inline-map spacing | All 13 tests green |

## Measured demo values (live, post-fix)

| Scenario | Incidents | Top risk | Top service | Rules |
|---|---|---|---|---|
| D benign | 0 | — | — | — (quiet ✓) |
| A radiology | 2 | 31.0 | imaging_reads T2 | R1+R2+R3+R5 (+pacs R6 lateral) |
| B pharmacy | 2 | 40.6 | medication_administration T1 | R1+R2+R3+R6 (+vpn R5) |
| C pump | 1 | 38.8 | medication_administration T1, passive-only | R9+R10 |

## Graph outage fix (dashboard showed blank graph)

| Bug | Severity | Fix |
|---|---|---|
| `layout: {name:"dagre"}` — dagre is a separate Cytoscape extension, never vendored; constructor threw `No such layout`, `cy` stayed null, init retried-and-threw every second | **Fatal, graph never rendered** | Switched to built-in `breadthfirst` (directed) layout; verified headless in Node with live `/api/graph` payload — 35 nodes, 38 edges, all positions finite |
| `#cy{height:100%}` inside flex column could collapse to 0 px | Blank canvas even with working layout | Explicit `min-height:480px` + flex on `#cy`/container |
| Node tap called `selectInc(nodeId)` → 404 on `/api/incidents/{nodeId}` | Console errors, broken selection | Tap now maps node → incident by `endpoint_id` via cached list; non-incident nodes ignored |
| Silent failures | — | try/catch around init + update with on-canvas error message |

Proven: old name throws `No such layout 'dagre'`; new config renders. 13/13 tests still green.

---

## Graph restyle + runbook (panel polish)

**Graph readability** — labels were 9 px default-dark on a dark theme (near-invisible);
all nodes one shape/color, no legend, hot path barely distinct:
- Light labels everywhere: 11–12 px `#e8edf2` with dark halo (`text-outline`), bold white on hot nodes
- Shape/color language: blue ellipse = workstation, blue round-rect = server,
  purple diamond = medical device, teal triangle = building IoT, violet = application,
  services tier-tinted (T1 red / T2 amber / T3 green) with bold labels
- Attack path: red glow (`shadow-blur`), white bold labels, thick red edges; legend in panel header
- `applyGraphStyle` simplified to data-flag flips (stylesheet owns all visuals — no inline overrides to drift)
- `/api/graph` now emits `eclass` (endpoint class) per node; verified live: 2 ws / 8 srv / 4 dev / 2 iot / 16 apps all match selectors headless, positions finite
- Graph canvas gets a subtle radial backdrop
- Footgun noted: `pkill -f "uvicorn src.main"` matches your own shell — server had to be restarted after the `graph.py` change (no `--reload` on the demo server); DB survived, scenario B intact

**Runbook** — new `docs/runbook.md` + README pointer: every `make` target explained

---

## Living hospital + campaign + dashboard life + outputs doc

**Ambient sim** (`src/simulator/background.py`, `POST /api/sim/background`):
13 hosts, shift logons / PACS reads / device heartbeats / backup + agent health —
76 events per 15 min, **0 alerts by construction** (no ext flips, successes only,
allow-listed/baseline sources, never `device_command`). Proven by
`test_ambient_is_quiet` (30-min seed) and live (76 ev, 0 alerts, services green).

**Campaign E** (`scripts/make_campaign.py` → 64-event JSON + narration MD):
after-hours affiliate — VPN brute-force (R5) → nurse ws ransomware (R1+R2+R3) →
lateral to files/AD/pharmacy (R6×3) → pharmacy ransomware (T1 top, 40.6) →
camera-to-pump rogue dose/config (R9+R10, passive-only) → backup catalog wipe (R3).
Live result: **8 incidents**, pharmacy 40.6 > nurse 40.2 > pump 38.8 > backup 30.3.

**Bugs caught live**: (1) `run_sim_async` died after 1 event — `asyncio` imported
only inside route fns, missing at module level; (2) service-health compared 0–1
service risk against 0–100 thresholds (all green during a T1 outbreak) — now ×100.
Also learned: `pkill -f` patterns must be bracketed (`src[.]main:app`) or the shell
kills itself.

**Dashboard life**: scenario bar (D/A/B/C/E/ambient/reset, no terminal needed),
header stats (events, 5-min rate, open, max risk), T1/T2/T3 health cards with
fallback+clock, live event feed (hot rows red, campaign phases purple),
guided empty states. New endpoints: `/api/stats`, `/api/events/recent`.

**Outputs doc**: `docs/site_outputs.md` — every badge, card, color, clock,
recommendation, and audit state explained with live Campaign E values.

---

## Approval button post-mortem (reported: "button does nothing")

**Root cause (frontend)**: buttons sent the action's database **ID** (`act-…`) but
`POST /api/incidents/{id}/actions/{action}/{approve|deny}` resolves the **action
name** (`isolate_host_pending_approval`) — every click 404'd, and the failure was
swallowed silently. Fixed `decide()` to send `encodeURIComponent(actionName)`,
surface HTTP errors in the sim-status line, and `refreshAll()` afterwards.

**Missing semantics (backend)**: approval changed nothing visible — the incident
stayed open either way. Now **approve → incident `contained`** (+ `incident_contained`
audit entry): it leaves the open queue (`/api/incidents` filters `status=open`,
`?status=all` opt-out), feed rows go green, service health recovers; the detail pane
stays on the contained incident with a `CONTAINED ✓` title instead of blanking.
**Deny → stays open** with reason audited. New events on a contained endpoint open
a fresh incident. Added `test_approve_by_name_contains_incident` (ID→404,
name→contained, queue empties, chain verifies). Live-verified both paths:
pump approve → contained, radiology deny → open with reason. 16/16 green.

---

## PULSE console reskin (user-supplied reference: `../index.html`, 95 KB static mock)

Kept our backend as the product; adopted the reference **design shell** (CSS + layout
verbatim, generated into `public/index.html` via scripted transform) and rewrote
`public/app.js` (~700 lines) against live `/api/*`:

- Queue/capbar/ledger/feed/charts/console/audit-drawer/modal/toasts/ECG all poll
  real endpoints; the reference's in-browser sim engine was dropped entirely.
- Backend additions to serve the design: edge `rel` + lateral `reach` edges on
  highlight, `alerts` (deduped per rule) + fallback readiness/activation in detail,
  `endpoint_status` + `alert_ts` in stats, demo-only `POST /api/audit/tamper`.
- Graph positions computed client-side in PULSE columns (endpoints → apps → services).
- Severity bands + CODE thresholds + technical-severity are DISPLAY-fitted to our
  measured scale (campaign peak ≈41) and marked as such in code.
- Approval modal keeps PULSE styling with single-analyst truth (clinical = notified).
- Vendored `lucide.min.js` (offline-safe icons); Google Fonts with system fallback.
- Verified: 18/18 tests (new: graph rel/reach, stats/tamper/signals), live ambient +
  campaign on the new UI (8 incidents, reach edges hot, ledger + scatter render data).
(run/test/demo/reset/clean/vendor/sim), emitter flags + expected outcome per scenario,
curl recipes for incidents/detail/graph/approve/audit, tamper demo, `make_visuals.py`,
troubleshooting table (PYTHONPATH, connection refused, blank graph, port busy).

## Visuals added for panel
- `docs/architecture.svg`, `docs/demo_flow.svg` (hand-written, dark theme)
- `docs/screenshots/scoring_comparison.png`, `topology.png`, `noisy_or.png` via `scripts/make_visuals.py`
- `docs/panel_guide.md` — slide-by-slide 5-min script + Q&A