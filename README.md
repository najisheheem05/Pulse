<p align="center">
  <img src="docs/Pulse.png" alt="Pulse logo" width="100">
  <h1 align="center">Pulse</h1>
</p>

### Hospital Impact Defense

Clinical-impact endpoint defense platform — watches every hospital endpoint, maps
attacks to the patient-care services at risk, ranks by clinical impact (not
technical severity), and routes disruptive containment through human approval.

## The problem

A SOC ranks alerts by technical severity. A ransomware burst on a radiology PC and
the *same* burst on the pharmacy server look identical — but one threatens
**imaging reads (Tier 2, 2-hour clock)** and the other threatens **medication
administration (Tier 1, 15-minute clock)**. Pulse ranks by what each endpoint can
take away from patients, traces the blast path through a hospital dependency
graph, and never auto-isolates a medical device.

## How it works

```
Simulator ──► POST /api/events ──► Detection (R1–R10, stateful rules + baselines)
                                        │  noisy-OR confidence per endpoint
                                        ▼
                                   Correlator ──► one incident per endpoint
                                        │  graph traversal to services at risk
                                        ▼
                                   Impact engine ──► clinical risk score + explanation
                                        │  playbook recommendation by tier
                                        ▼
                                   Human approval ──► contained / stays open
                                        │  every step hash-chained
                                        ▼
                                   PULSE dashboard (1 s polling, works offline)
```

## Features

- **All endpoint classes**: workstations + servers (agent-style JSON telemetry) and
  infusion pumps, monitors, vents, scanners, cameras, printers (passive flow /
  protocol telemetry) — one unified event schema.
- **7 ATT&CK-mapped rules** (R1, R2, R3, R5, R6, R9, R10) with thresholds, weights,
  allow-lists, and device baselines in `data/rules.yaml` — no code changes to retune.
- **Correlator**: alerts on one endpoint within a window become a single incident;
  confidence is noisy-OR, so R1+R2+R3 (≈0.99) dwarfs R1 alone (0.60).
- **Impact engine**: `networkx` traversal endpoint → app → service, plus lateral
  segment reachability (flagged *potential*, scored ×0.3); plain-English explanation
  with fallback procedure and deadline per incident.
- **Human-in-the-loop**: playbook recommendation by tier → analyst approve/deny in
  a two-click modal → approve contains the incident, deny keeps it open with a
  reason. Medical devices are never auto-contained.
- **Tamper-evident audit**: SHA-256 hash-chained log with one-click verify and a
  demo tamper button that turns the badge red live.
- **PULSE dashboard**: facility pulse/ECG + CODE level, ranked queue with budget
  countdowns, layered dependency graph (attack path red, lateral reach amber,
  endpoint dossiers), impact ledger (clinical-vs-technical scorebox, ATT&CK strip,
  feasibility tags), live telemetry feed, analytics (alert-rate, severity≠impact
  scatter, posture), scenario console (A/B/C/D/E, ambient, guided, reset).
- **Living-hospital simulation**: ambient normal traffic generator (fires nothing
  by construction) plus a 64-event connected kill chain (vendor VPN → nurse
  workstation → pharmacy server → infusion pump → backup wipe).

## Quick start

```bash
pip install -r requirements.txt
make run                # API + dashboard on http://localhost:8000
```

Then either click buttons in the dashboard's demo console, or drive it from a
second terminal:

```bash
make demo SCENARIO=d         # benign patching — expect 0 incidents
make demo SCENARIO=a         # radiology ransomware — imaging T2
make demo SCENARIO=b         # pharmacy ransomware — medication T1
make demo SCENARIO=c         # rogue pump command — passive-only
make demo SCENARIO=campaign  # ambient hospital + connected kill chain (recommended)
```

Open <http://localhost:8000> — the console polls live; no refresh needed.

## Demo flows

**Classic 5-minute tour** (`make demo SCENARIO=full` runs D→A→B→C with resets):

| Time | Action | Expected |
|---|---|---|
| 0:00 | Scenario D | 0 incidents — honest false-positive handling |
| 0:30 | Scenario A | ≈31, `rad-ws-02 → pacs → imaging_reads` (T2), Local DICOM viewer fallback |
| 1:45 | Scenario B (after reset) | ≈40.6, `pharm-srv-01 → pharmacy → medication_administration` (T1), 15-min clock |
| 3:00 | Scenario C (after reset) | ≈38.8, pump incident, passive-monitoring-only, approval required |
| 4:00 | Approve → tamper → verify | Chain badge flips red live |

**Recommended run** (the before/after contrast): press **AMBIENT** (hospital wakes
up, services green, 0 incidents), then **E CAMPAIGN** — 64 events land in seconds,
feed narrates P1→P6 in purple, pharmacy + pump take the top slots. Click the
pharmacy card: *"One vendor password. Forty-eight minutes. Pharmacy, pumps, and
backups."* Then approve the isolation and tamper the ledger.

## Measured results (live, Campaign E + ambient)

| Scenario | Incidents | Top risk | Top service | Rules |
|---|---|---|---|---|
| D benign patching | 0 | — | — | quiet ✓ |
| A radiology WS | 2 | 31.0 | imaging_reads T2 (+PACS lateral R6) | R1+R2+R3+R5 |
| B pharmacy server | 2 | 40.6 | medication_administration T1 (+VPN entry R5) | R1+R2+R3+R6 |
| C infusion pump | 1 | 38.8 | medication T1, passive-only | R9+R10 |
| E campaign (64 events) | 8 | 40.6 → 40.2 → 38.8 → 30.3 | pharmacy, nurse WS, pump, backup (all T1 paths) | R5 → R1-3 → R6×3 → R1-3 → R9/R10 → R3 |
| Ambient (76 events/15 min) | 0 | — | all services operational | none (by construction) |

## Architecture

| Component | File | Responsibility |
|---|---|---|
| API | `src/main.py` | 15 routes, static dashboard |
| Schema | `src/core/schema.py` | Pydantic `Event` / `Alert` / `Incident` — one format for agent + passive |
| Store | `src/core/store.py` | SQLite via stdlib (`events, alerts, incidents, actions, audit`) |
| Detection | `src/detection/engine.py` | R1, R2, R3, R5, R6, R9, R10 over per-endpoint event windows |
| Baselines | `src/detection/baseline.py` | IoMT/IoT allow-lists + maintenance-window check |
| Correlator | `src/detection/correlate.py` | Per-endpoint grouping, noisy-OR confidence |
| Graph | `src/impact/graph.py` | `networkx` DiGraph from YAML; paths + lateral reach; Cytoscape JSON |
| Scoring | `src/impact/scoring.py` | Clinical risk formula (below) |
| Explain | `src/impact/explain.py` | Human-readable incident narratives |
| Playbooks | `src/response/playbooks.py` | Risk-tiered action recommendations |
| Approvals | `src/response/approvals.py` | Single-analyst approve/deny queue |
| Audit | `src/response/audit.py` | SHA-256 hash chain (~30 lines of crypto) |
| Simulator | `src/simulator/emitter.py` | Scenario replay to `POST /api/events` |
| Ambient | `src/simulator/background.py` | Normal-traffic generator (quiet by design) |

## Endpoint classes

| Class | Examples | Agent? | Telemetry | Key rules |
|---|---|---|---|---|
| Workstations | nurse station, radiology PC | Yes | process, file, logon (Sysmon-style JSON) | R1, R2, R3, R5 |
| Servers | EHR, PACS, LIS, pharmacy, AD, backup, VPN jump | Yes | same + RDP/SMB logons | R1, R3, R5, R6 |
| Medical devices (IoMT) | infusion pump, monitor, vent, CT | **No** | passive flow / protocol records | R9, R10 |
| Building IoT | cameras, printers | **No** | passive flow records | R9 (+R6 pivot trail) |

A pump can't run an agent — that split is the core design decision: agent hosts
get behavioral rules, agentless devices get baselines + command allow-lists.

## Detection rules

| ID | Rule | Signal | ATT&CK | Weight |
|---|---|---|---|---|
| R1 | Mass rename/modify burst | ≥15 file ops in 120 s **with ≥3 extension flips** to `.locked/.enc` (flip gate keeps patching quiet) | T1486 | 0.60 |
| R2 | Canary file touched | Any write to a canary path | T1486 | 0.80 |
| R3 | Recovery inhibition | `vssadmin`/`wbadmin`/`bcdedit`/backup-delete patterns, or catalog wipe / job disable | T1490 | 0.70 |
| R5 | Brute force → success | ≥5 failures then success, same user, 10 min | T1110/T1078 | 0.55 |
| R6 | New RDP/SMB source | Logon from IP outside the server's allow-list (guest-VLAN sources always rogue) | T1021.001/.002 | 0.60 |
| R9 | Device baseline deviation | Flow to dst/port/proto outside the learned per-device baseline | — (baseline) | 0.65 |
| R10 | Unauthorized device command | Command from non-allow-listed source, or config command outside 02:00–04:00 window | T0855 | 0.85 |

Confidence per incident: `1 − Π(1 − wᵢ)` — e.g. R1+R2+R3 = `1 − 0.4×0.2×0.3 ≈ 0.976`.
R4, R7, R8, R11, R12 are documented stretch, not implemented (see
`docs/detection-rules.md`). Verify ATT&CK IDs at attack.mitre.org before citing —
they were assigned from memory.

## Hospital model & scoring

`data/hospital.yaml` defines 16 endpoints → 16 applications → 3 services
(`medication_administration` T1/15 min/Paper MAR, `imaging_reads` T2/120 min/Local
DICOM, `patient_scheduling` T3/480 min/Phone) across 5 network segments with
lateral reachability, plus tier weights and fallback readiness (all hand-assigned —
see Limitations).

```
exposure       = 1.0 direct | 0.6 dependency | 0.3 lateral (potential)
service_risk   = tier_weight × (1 − fallback_readiness) × exposure × confidence
incident_risk  = min(100, max(service_risk)×100 + 0.1 × Σ others×100)
```

Worked example (same malware, different rank): R1+R2+R3 on `rad-ws-02`
(conf 0.976, dependency path to imaging T2: `0.6 × 0.5 × 0.6 × 0.976 ≈ 0.176`)
→ **31.0**; on `pharm-srv-01` (direct path to medication T1:
`1.0 × 0.4 × 1.0 × 0.99`) → **40.6**. Identical techniques, different patients.

## Response & approvals

| Situation | Recommended action | Gate |
|---|---|---|
| Low risk | Raise alert, snapshot logs, increase logging | automatic |
| Medium (T2 band) | Disable user, block outbound | analyst approves |
| High / Tier-1 | Isolate host / segment change (clinical chair notified) | analyst approves |
| Medical device, any tier | Passive monitoring + gateway ACL review | approval required — **never auto-contained** |

Approve flips the incident to `contained` (leaves the queue, feed greens, service
health recovers); deny keeps it open with an audited reason. New events on a
contained endpoint open a fresh incident (re-infection story).

## Audit chain

Every detection, upsert, approval, denial, and reset appends a SHA-256-linked entry.
`GET /api/audit/verify` recomputes the chain; the dashboard badge flips red live
on mismatch. Try it: press **TAMPER (DEMO)** in the audit drawer, then
**VERIFY CHAIN** — or `POST /api/audit/tamper` (demo-only endpoint) followed by
`curl localhost:8000/api/audit/verify` → `{"ok":false,"tampered_seq":…}`.

## API reference

| Method & route | Purpose |
|---|---|
| `POST /api/events` | Ingest one unified-schema event (runs detection → correlation → impact) |
| `GET /api/incidents` | Open queue, ranked (`?status=all` includes contained) |
| `GET /api/incidents/{id}` | Detail: alerts, paths, services, explanation, recommendation, actions |
| `POST /api/incidents/{id}/actions/{action}/approve` | Approve by action **name** → incident `contained` |
| `POST /api/incidents/{id}/actions/{action}/deny` | Deny with reason → stays open |
| `GET /api/graph` | Cytoscape JSON (`?highlight_inc=` marks the attack path + reach edges) |
| `POST /api/sim/start?scenario=` | Replay `a/b/c/d/e` (prefix match on `data/scenarios/`) |
| `POST /api/sim/background?minutes=&seed=` | Ambient normal traffic (fires nothing) |
| `POST /api/sim/reset` | Wipe state (ledger survives — append-only) |
| `GET /api/stats` | Counters, per-service health, endpoint status, alert timestamps |
| `GET /api/events/recent?limit=` | Newest-first event feed with compromise flags |
| `GET /api/audit` · `GET /api/audit/verify` | Ledger + chain check |
| `POST /api/audit/tamper` | **Demo only**: corrupt one entry to show verification failing |

## Dashboard

The PULSE console (all live, 1 s polling): facility pulse/ECG tracking the CODE
level · scenario captions + counters · ranked queue with budget countdowns ·
layered graph with dossiers · impact ledger with feasibility tags and approval
modal · telemetry feed · analytics (alert-rate, severity≠impact scatter, posture) ·
console (A/B/C/D/E, ambient, guided, reset) · audit drawer.
What everything means: **`docs/site_outputs.md`** · what every control does:
**`docs/ui_features.md`**.

## Project structure

```
hospital-impact-defense/
├── README.md  LICENSE  .env.example  Makefile  requirements.txt  WORKLOG.md
├── data/
│   ├── hospital.yaml            # endpoints, apps, services, tiers, segments, weights
│   ├── rules.yaml               # thresholds, weights, allow-lists, baselines
│   └── scenarios/               # a_radiology, b_pharmacy, c_infusion_pump,
│                                # d_benign_patching, e_hospital_campaign (+.md narration)
├── src/
│   ├── main.py                  # FastAPI app + routes
│   ├── core/schema.py  core/store.py
│   ├── detection/engine.py  baseline.py  correlate.py  rules/   # rule stubs + docs
│   ├── impact/graph.py  scoring.py  explain.py
│   ├── response/playbooks.py  approvals.py  audit.py
│   └── simulator/emitter.py  background.py
├── scripts/demo.sh  make_campaign.py  make_visuals.py
├── tests/test_smoke.py          # 18 tests: rules, correlator, impact, audit, API flows
├── public/                      # PULSE console (index.html shell + app.js, vendored JS)
└── docs/                        # architecture, threat-model, detection-rules,
                                 # impact-scoring, limitations, runbook, site_outputs,
                                 # ui_features, panel_guide, visuals + screenshots
```

## Configuration

- `DATABASE_PATH` (default `hospital.db`), `PORT` — via environment / `.env`
  (see `.env.example`).
- Retune without code: thresholds, rule weights, RDP allow-lists, device baselines,
  maintenance window in `data/rules.yaml`; topology, tiers, fallbacks, segments in
  `data/hospital.yaml`; rebuild the campaign with `python3 scripts/make_campaign.py`
  and charts with `python3 scripts/make_visuals.py`.

## Testing & verification

```bash
make test          # 18 tests, ~1 s: 7 rules, noisy-OR, scoring, explain,
                   # playbooks, audit chain + tamper, scenario + campaign rules,
                   # ambient-quiet, approve-by-name API flow, stats/tamper API
```

Plus headless-Chromium console checks (zero JS errors) and live end-to-end runs of
every scenario before presenting — see `WORKLOG.md` for the full build +
debug log.

## Docs index

| Doc | Contents |
|---|---|
| `docs/architecture.md` | Components, storage schema, technology choices |
| `docs/threat-model.md` | Assets, adversary capabilities, coverage, gaps |
| `docs/detection-rules.md` | Rule reference + correlator math |
| `docs/impact-scoring.md` | Formula with worked A/B/C examples |
| `docs/runbook.md` | Every command, emitter flags, curl recipes, troubleshooting |
| `docs/site_outputs.md` | What every number/badge/color means |
| `docs/ui_features.md` | What every button/control does |
| `docs/panel_guide.md` | 5-minute panel script + anticipated Q&A |
| `docs/limitations.md` | Assumptions and non-goals |
| `WORKLOG.md` | Hour-by-hour build log + post-mortems |

## Visuals (for the panel)

| File | What |
|---|---|
| `docs/screenshots/pulse_console.png` | The live console mid-campaign (CODE DARK) |
| `docs/screenshots/scoring_comparison.png` | D=0, A=31 (T2), C=38.8 (T1 device), B=40.6 (T1) — the punchline |
| `docs/screenshots/topology.png` | Hospital dependency graph, attack paths in red |
| `docs/screenshots/noisy_or.png` | R1 → R1+R2 → R1+R2+R3 confidence stacking |
| `docs/architecture.svg` · `docs/demo_flow.svg` | Pipeline diagram · 5-minute timeline |

## Limitations (for judges)

1. **"Patient harm" = service impact proxy.** Tiers, downtimes, fallback readiness
   are hand-assigned assumptions requiring clinician validation.
2. **Circular detection.** Simulator and rules share an author — architecture PoC,
   no real-world precision/recall figures.
3. **Synthetic baselines.** Device "normal" is generated, not observed; no drift
   handling.
4. **Simulated agent telemetry.** Production needs Sysmon/EDR + Zeek on SPAN and
   parsers for HL7/DICOM/proprietary protocols.
5. **No malware.** The simulator emits JSON only — nothing encrypts, nothing breaks.
6. **Single-analyst approval**, static YAML graph, single-hospital SQLite —
   demo scope, not production posture (see `docs/limitations.md`).

## License

MIT — see `LICENSE`.
