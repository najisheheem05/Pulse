# Runbook — how to run, what each command does

> One-time setup: `pip install -r requirements.txt` (fastapi, uvicorn, pydantic,
> pyyaml, networkx, pytest, httpx). All commands run from the repo root.

## Make targets (`make <target>`)

| Command | What it does | When to use it |
|---|---|---|
| `make run` | Starts the API + dashboard: `PYTHONPATH=. uvicorn src.main:app --reload --host 0.0.0.0 --port 8000`. `--reload` restarts on code edits. Dashboard at http://localhost:8000 | Always first — everything else needs the server |
| `make demo` | Runs one scenario file through the simulator: `make demo SCENARIO=<name>`. Default `SCENARIO=full` runs D→A→B→C with resets between; `campaign` = ambient traffic + Campaign E | The panel demo |
| `make test` | Runs the suite: `pytest -q` (13 tests: 7 rules, correlator, scoring, explain, playbook, audit, scenario) | Before presenting, after any edit |
| `make reset` | Clears all state: `POST /api/sim/reset` (wipes events, alerts, incidents, actions, audit) | Between scenarios, before the panel |
| `make clean` | Deletes `hospital.db` + `__pycache__` (full local wipe; server recreates the DB on boot) | Fresh start / before zipping the repo |
| `make vendor` | Re-downloads `htmx.min.js` + `cytoscape.min.js` into `public/vendor/` (offline-safe demo) | Only if you deleted `public/vendor/` |
| `make sim` | Prints simulator help (`python3 -m src.simulator.emitter --help`) | Discover emitter flags |

## Simulator (`python3 -m src.simulator.emitter`)

Replays a scenario JSON (`data/scenarios/*.json`) event-by-event via `POST /api/events`.

```bash
export PYTHONPATH=$(pwd)   # required: makes `src.*` imports resolve
python3 -m src.simulator.emitter a_radiology --delay 50
python3 -m src.simulator.emitter b_pharmacy --delay 50 --no-reset   # layer onto existing state
```

| Argument | Meaning |
|---|---|
| `a_radiology` (or `a`) | Ransomware on `rad-ws-02` → expect incident ≈31, imaging_reads T2 |
| `b_pharmacy` (or `b`) | Same behavior on `pharm-srv-01` → expect ≈40.6, medication T1, 15-min clock |
| `c_infusion_pump` (or `c`) | Rogue `dose_rate`/`set_config` to `pump-icu-04` → expect ≈38.8, passive-only |
| `d_benign_patching` (or `d`) | Patching + backup noise → expect **0 incidents** (honest negative) |
| `e_hospital_campaign` (or `e`) | 64-event connected kill chain (VPN brute-force → nurse ws ransomware → lateral to files/AD/pharmacy → pharmacy ransomware → camera-to-pump pivot → backup wipe). Rebuild with `python3 scripts/make_campaign.py`; narration in `data/scenarios/e_hospital_campaign.md` → expect **7 incidents**, pharmacy + pump T1 on top |
| `--delay N` | Milliseconds between events (default 50; use 5–10 for a fast demo) |
| `--no-reset` | Skip the automatic `POST /api/sim/reset` first (default: reset, so each run starts clean) |
| `--url URL` | Point at a non-local server (default http://localhost:8000) |

`scripts/demo.sh` is a thin wrapper: `SCENARIO=<name|full> bash scripts/demo.sh`
(`full` = D, reset, A, reset, B, reset, C, then audit verify).

## API spot-checks (curl recipes)

```bash
BASE=http://localhost:8000
curl -s $BASE/api/incidents | python3 -m json.tool                       # open queue, ranked (by risk_score desc)
curl -s "$BASE/api/incidents?status=all" | python3 -m json.tool            # includes contained/closed
curl -s $BASE/api/incidents/<inc-id> | python3 -m json.tool             # alerts, path, explanation, recommendation, actions
curl -s "$BASE/api/graph?highlight_inc=<inc-id>" | python3 -m json.tool # Cytoscape nodes/edges, attack path has "hot": true
curl -s $BASE/api/stats | python3 -m json.tool                          # header badges + service health (drives dashboard top strip)
curl -s "$BASE/api/events/recent?limit=25" | python3 -m json.tool        # live event feed (hot = on compromised endpoint)
curl -s -X POST "$BASE/api/sim/background?minutes=15&seed=7"             # ambient hospital traffic (fires nothing)
curl -s -X POST $BASE/api/audit/tamper                                    # DEMO ONLY: corrupt one ledger entry, then verify fails
curl -s -X POST $BASE/api/incidents/<id>/actions/<action>/approve \
  -H 'Content-Type: application/json' -d '{"approver":"analyst"}'        # approve (use /deny to deny)
curl -s $BASE/api/audit | python3 -m json.tool                           # hash-chained log (newest first)
curl -s $BASE/api/audit/verify                                           # {"ok":true,...} or {"ok":false,"tampered_seq":N}
```

Every number on the dashboard is explained field-by-field in **`docs/site_outputs.md`**.

## Tamper demo (the 45-second closer)

```bash
sqlite3 hospital.db "UPDATE audit SET payload='hacked' WHERE seq=1;"
curl -s http://localhost:8000/api/audit/verify   # -> {"ok":false,"tampered_seq":1,...}
curl -s -X POST http://localhost:8000/api/sim/reset  # restores a clean chain
```

## Regenerating panel visuals

```bash
python3 scripts/make_visuals.py   # rewrites docs/screenshots/*.png from data + measured scores
```

SVGs (`docs/architecture.svg`, `docs/demo_flow.svg`) are hand-written — edit directly.

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `ModuleNotFoundError: No module named 'src'` | `PYTHONPATH` not set → `export PYTHONPATH=$(pwd)` (Makefile already does this for `make run`) |
| `Connection refused` from emitter | Server isn't up → `make run` first, in another terminal |
| Graph panel blank | Hard-refresh (Ctrl+Shift+R); check DevTools console; `curl $BASE/api/graph` must return nodes/edges |
| Incidents pile up across scenarios | `make reset` (or re-run emitter without `--no-reset`) |
| Port 8000 busy | `PORT=8001 make run` won't work (port is hardcoded) — kill the old server: `pkill -f "uvicorn src.main"` |
