# Panel Presentation Guide (5 minutes + Q&A)

## Slide 1 — Problem (30 s)
Hospitals rank alerts by **technical severity**. A ransomware burst on a radiology PC
and on the pharmacy server look identical to the SOC — but one threatens
**imaging reads (T2, 2 h clock)** and the other threatens **medication
administration (T1, 15 min clock)**. We rank by **clinical impact**.

Show: `docs/architecture.svg`

## Slide 2 — Architecture (30 s)
Simulator → normalizer → detection (R1–R10) → correlator (noisy-OR) →
impact graph → response queue → hash-chained audit. Static dashboard, 1 s polling,
works offline (vendored JS).

## Slide 3 — Live: honest negative (30 s)
`SCENARIO=d bash scripts/demo.sh` → **0 incidents**. Patching + backup traffic
does not fire: R1 requires extension flips, R6 allow-lists known hosts.

## Slide 4 — Live: radiology (75 s)
Scenario A → incident **risk 31**, `rad-ws-02 → pacs_viewer → pacs → imaging_reads`.
Graph path in red. Fallback: **Local DICOM viewer**, 120-min clock. Action needs approval.

Show: `docs/screenshots/topology.png`

## Slide 5 — Live: pharmacy, same malware, different rank (75 s)
Scenario B → incident **risk 40.6**, `pharm-srv-01 → pharmacy → medication_administration`
**Tier 1, 15-min deadline**. Same R1+R2+R3, wildly different rank — **that is the product**.

Show: `docs/screenshots/scoring_comparison.png`

## Slide 6 — Live: pump (60 s)
Scenario C → **risk 38.8**, `pump-icu-04 → infusion_mgmt → medication_administration`.
Passive telemetry only. Recommendation: **passive monitoring + segmentation change,
approval required — never auto-isolate a medical device**.

## Slide 7 — Live: approve + tamper (45 s)
Approve the isolation → audit entry. Then `UPDATE audit SET payload='hacked'` →
`GET /api/audit/verify` → **`{"ok": false}`**. ~30 lines of SHA-256 chain.

Show: `docs/screenshots/noisy_or.png` during Q&A for correlator questions.

## Anticipated Q&A
- *"Is this real detection?"* — No: circular PoC, same author wrote sim + rules. Architecture is the contribution.
- *"Patient harm?"* — Proxy: service impact with hand-assigned tiers. Needs clinician validation.
- *"Why not auto-isolate the pump?"* — Patient-safety interlock: devices are never auto-contained.
- *"What breaks first at scale?"* — SQLite writes; graph is static YAML (no discovery).
- *ATT&CK IDs* — verify at attack.mitre.org before submission; given from memory.
