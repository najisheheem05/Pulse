# Architecture

## Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌─────────────┐
│  Simulator  │────►│  FastAPI     │────►│  Normalizer     │────►│  Detection  │
│ (scenarios) │     │  /api/events │     │  (schema)       │     │  Engine     │
└─────────────┘     └──────────────┘     └─────────────────┘     └──────┬──────┘
                                                                        │
                    ┌─────────────────┐     ┌─────────────────┐         │
                    │  Response &     │◄────│  Impact Engine  │◄────────┘
                    │  Approvals      │     │  (graph+score)  │
                    └────────┬────────┘     └─────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Audit Chain    │  (SHA-256 hash-chained log)
                    └─────────────────┘
```

## Components

| Component | File | Responsibility |
|---|---|---|
| API | `src/main.py` | 8 routes, static dashboard |
| Schema | `src/core/schema.py` | Pydantic Event/Alert/Incident |
| Store | `src/core/store.py` | SQLite CRUD (stdlib) |
| Detection | `src/detection/engine.py` | 7 MVP rules over event windows |
| Baseline | `src/detection/baseline.py` | IoMT/IoT allow-lists |
| Correlator | `src/detection/correlate.py` | 30m window, noisy-OR confidence |
| Graph | `src/impact/graph.py` | networkx DiGraph from hospital.yaml |
| Scoring | `src/impact/scoring.py` | Clinical risk formula |
| Explain | `src/impact/explain.py` | Human-readable narratives |
| Playbooks | `src/response/playbooks.py` | Risk-tiered action recommendations |
| Approvals | `src/response/approvals.py` | Single-analyst approve/deny |
| Audit | `src/response/audit.py` | SHA-256 hash chain (~30 lines) |
| Simulator | `src/simulator/emitter.py` | Scenario replay to POST /api/events |

## Storage Schema

```sql
events(id, ts, endpoint_id, endpoint_class, source, event_type, user, details)
alerts(id, ts, endpoint_id, rule_id, title, severity, confidence, attack, details)
incidents(id, endpoint_id, created_at, updated_at, rule_ids, alert_count, confidence, risk_score, services, paths, explanation, status)
actions(id, incident_id, action, risk_tier, status, requested_at, decided_at, approver, reason)
audit(seq, ts, actor, action, incident_id, payload, prev_hash, hash)
```

## Technology Choices

- **Python 3.12+ / FastAPI / Pydantic** — typed schemas double as API docs
- **SQLite (stdlib)** — zero-setup, single file, sufficient for demo scale
- **networkx + YAML** — graph traversal in ~50 lines
- **htmx + Cytoscape.js (vendored)** — no build step, works offline
- **1-second polling** — simpler than WebSockets under time pressure