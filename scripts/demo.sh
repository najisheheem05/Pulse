#!/bin/bash
# Panel demo: D (quiet) -> A (radiology) -> B (pharmacy T1) -> C (pump) -> audit tamper,
# or: ambient + E campaign (connected kill chain in a living hospital)
# Usage: SCENARIO=e bash scripts/demo.sh   (a|b|c|d|e|full|campaign|ambient)
set -e
BASE="${BASE:-http://localhost:8000}"
SC="${SCENARIO:-full}"
export PYTHONPATH="$(pwd)"

run_scenario() {
  echo "=== scenario $1 ==="
  python3 -m src.simulator.emitter "$1" --delay 5
  echo "--- incidents ---"
  curl -s "$BASE/api/incidents" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} incident(s)'); [print(' ',x['id'],x['endpoint_id'],'risk='+str(x['risk_score']),x['rule_ids']) for x in d]"
}

case "$SC" in
  full)
    run_scenario d_benign_patching
    echo; echo ">>> D should show 0 incidents (honest FP handling). Resetting..."
    curl -s -X POST "$BASE/api/sim/reset" > /dev/null; echo "reset ok"
    run_scenario a_radiology
    echo; echo ">>> A: medium-high, imaging_reads T2. Resetting..."
    curl -s -X POST "$BASE/api/sim/reset" > /dev/null; echo "reset ok"
    run_scenario b_pharmacy
    echo; echo ">>> B: CRITICAL, medication_administration T1, 15-min clock. Resetting..."
    curl -s -X POST "$BASE/api/sim/reset" > /dev/null; echo "reset ok"
    run_scenario c_infusion_pump
    echo; echo ">>> C: pump alert, passive-only. Verify audit:"
    curl -s "$BASE/api/audit/verify"; echo
    ;;
  campaign)
    echo "=== ambient first: wake the hospital ==="
    curl -s -X POST "$BASE/api/sim/background?minutes=15&seed=7"; echo
    run_scenario e_hospital_campaign
    echo; echo ">>> E: 7 incidents — pharmacy + pump T1 on top. Verify audit:"
    curl -s "$BASE/api/audit/verify"; echo
    ;;
  ambient)
    curl -s -X POST "$BASE/api/sim/background?minutes=${MINUTES:-15}&seed=7"; echo
    ;;
  a) run_scenario a_radiology ;;
  b) run_scenario b_pharmacy ;;
  c) run_scenario c_infusion_pump ;;
  d) run_scenario d_benign_patching ;;
  e) run_scenario e_hospital_campaign ;;
  *) run_scenario "$SC" ;;
esac
