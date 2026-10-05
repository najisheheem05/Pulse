# Hospital Impact Defense

Clinical-impact endpoint defense platform — watches every hospital endpoint, maps attacks to patient-care services at risk, ranks by clinical impact (not technical severity), and routes disruptive containment through human approval.

## Quick Start

```bash
make run                # starts API on http://localhost:8000
# in another terminal (or use the dashboard's scenario bar):
make demo SCENARIO=d    # benign patching (no alert)
make demo SCENARIO=a    # radiology ransomware
make demo SCENARIO=b    # pharmacy ransomware (Tier-1)
make demo SCENARIO=c    # infusion pump command
make demo SCENARIO=campaign  # ambient hospital + connected 64-event kill chain (recommended)
```

Open http://localhost:8000 → dashboard auto-loads.

## Architecture

```
Simulator ──► POST /api/events ──► Normalizer ──► Detection (R1-R10)
                                                    │
                                           Correlator (30m window)
                                                    │
                                           Impact Engine (graph traversal)
                                                    │
                                           Response + Approvals (audit chain)
```

## Detection Rules (MVP)

| ID | Rule | ATT&CK | Target |
|---|---|---|---|
| R1 | Mass rename/modify burst | T1486 | workstation, server |
| R2 | Canary file touched | T1486 | workstation, server |
| R3 | Recovery inhibition | T1490 | workstation, server, backup |
| R5 | Brute force → success | T1110/T1078 | all with auth |
| R6 | New RDP/SMB source | T1021.001/.002 | servers |
| R9 | Device baseline deviation | baseline | IoMT, IoT |
| R10 | Unauthorized device command | T0855 | IoMT |

*R4, R7, R8, R11, R12 are stretch — not implemented.*

## Hospital Model & Scoring

`data/hospital.yaml` defines:
- **Endpoints** (16): workstations, servers, pumps, monitors, vents, CT, cameras, printers
- **Applications** (16): EHR, PACS, LIS, Pharmacy, AD, backup, device mgmt, etc.
- **Services** (3): medication_administration (T1), imaging_reads (T2), patient_scheduling (T3)
- **Segments** with lateral reachability

**Scoring** (weights in YAML):
```
exposure = 1.0 direct | 0.6 dependency | 0.3 lateral (potential)
service_risk = tier_weight × (1−fallback_readiness) × exposure × detection_confidence
incident_risk = max(service_risk) + 0.1 × sum(others), capped at 100
```

Tier weights: T1=1.0, T2=0.6, T3=0.3

## Response Playbooks

| Risk | Action | Approval |
|---|---|---|
| Low | raise alert, snapshot logs, increase logging | auto |
| Medium (T2, 15–40) | disable user, block outbound | analyst |
| High/T1 (≥40 or T1) | isolate host, ACL change | analyst (+ clinical notify) |
| **Medical device** | passive monitoring + segmentation review | **required**, never auto |

## Audit Chain

Every decision → hash-chained log. `GET /api/audit/verify` proves tampering.

```bash
# tamper demo:
sqlite3 hospital.db "UPDATE audit SET payload='hacked' WHERE seq=1;"
curl localhost:8000/api/audit/verify  # {"ok":false,"tampered_seq":1}
```

## 5-Minute Demo Script

| Time | Action | Expected |
|---|---|---|
| 0:00 | `make demo SCENARIO=d` | No incident — honest FP handling |
| 0:30 | `make demo SCENARIO=a` | Medium-high incident, rad-ws-02 → PACS → imaging_reads (T2), fallback: Local DICOM viewer |
| 1:45 | `make reset && make demo SCENARIO=b` | **Critical** incident, pharm-srv-01 → pharmacy/EHR → medication_administration (T1), 15-min deadline clock |
| 3:00 | `make reset && make demo SCENARIO=c` | Pump alert, **passive-only** recommendation, approval required |
| 4:00 | Approve isolate → `GET /audit/verify` → tamper → verify fails | Hash-chain proof |

## Make Targets

```bash
make run        # API + dashboard on :8000 (needs server first for everything below)
make demo SCENARIO=a  # a|b|c|d|full (default full = D→A→B→C with resets)
make test       # pytest -q (13 tests)
make reset      # wipe all state via POST /api/sim/reset
make vendor     # re-download htmx + cytoscape into public/vendor/
make clean      # delete hospital.db + __pycache__
```

Full command reference — what each command does, emitter flags, curl recipes,
tamper demo, troubleshooting: **`docs/runbook.md`**.

## Project Structure

```
hospital-impact-defense/
├── README.md LICENSE .env.example Makefile requirements.txt .gitignore
├── data/
│   ├── hospital.yaml      # nodes, edges, tiers, fallbacks, segments
│   ├── rules.yaml         # thresholds, weights, allow-lists
│   └── scenarios/         # a_radiology.json b_pharmacy.json c_infusion_pump.json d_benign_patching.json
├── src/
│   ├── main.py            # FastAPI + 8 routes
│   ├── core/schema.py     # Event/Alert/Incident Pydantic models
│   ├── core/store.py      # SQLite (stdlib) CRUD
│   ├── detection/engine.py   # R1,R2,R3,R5,R6,R9,R10
│   ├── detection/baseline.py # IoMT/IoT baselines
│   ├── detection/correlate.py # noisy-OR confidence
│   ├── impact/graph.py    # networkx DiGraph from YAML
│   ├── impact/scoring.py  # clinical risk formula
│   ├── impact/explain.py  # plain-English narratives
│   ├── response/playbooks.py # risk-tiered actions
│   ├── response/approvals.py # single-analyst queue
│   ├── response/audit.py  # SHA-256 hash chain
│   └── simulator/emitter.py # scenario replay
├── tests/test_smoke.py    # 13 tests: rules, impact, audit
└── public/
    ├── index.html         # dashboard (htmx + cytoscape)
    └── app.js             # 1s polling, ranked list + graph + approvals
```

## Dashboard (PULSE console)

Top bar with facility pulse (ECG follows the CODE level: nominal → watch → alert →
code dark) · capability bar with scenario captions and live counters · incident
queue ranked by clinical impact with budget countdowns · layered dependency graph
(endpoints → apps → services; red attack path, amber lateral-reach, blast dimming,
endpoint dossiers on click) · impact ledger (scorebox clinical-vs-technical,
ATT&CK progression, propagation steps, service cards with feasibility tags,
signals, two-click human approval modal) · telemetry feed · analytics
(alert-rate, severity≠impact scatter, posture) · demo console (A/B/C/D/**E**,
ambient, guided, reset) · audit drawer with one-click verify + tamper demo.
Field-by-field meaning of everything on screen: **`docs/site_outputs.md`**.

## Visuals (for the panel)

| File | What |
|---|---|
| `docs/architecture.svg` | Pipeline diagram (dark, panel-ready) |
| `docs/demo_flow.svg` | 5-minute demo timeline with expected scores |
| `docs/screenshots/scoring_comparison.png` | D=0, A=31 (T2), C=38.8 (T1 device), B=40.6 (T1) — the punchline |
| `docs/screenshots/topology.png` | Full hospital dependency graph, attack paths in red |
| `docs/screenshots/noisy_or.png` | R1 → R1+R2 → R1+R2+R3 confidence stacking |
| `docs/panel_guide.md` | Slide-by-slide 5-minute script + anticipated Q&A |

Regenerate charts: `python3 scripts/make_visuals.py`

## Limitations (for judges)

1. **"Patient harm" = service impact proxy.** Tiers and fallback readiness are hand-assigned assumptions requiring clinician validation.
2. **Circular detection.** Simulator and rules written by same author — no real-world accuracy figures.
3. **Device baselines learned from synthetic "normal" traffic only.**
4. **Agent telemetry simulated.** Real deployment needs Sysmon/EDR + Zeek on SPAN.
5. **No encryption/ransomware code** — simulator emits synthetic JSON only.

## License

MIT — see `LICENSE`.