# Site Outputs — what every number, badge, and color means

Dashboard: http://localhost:8000 — the **PULSE console**.
Layout: top bar → capability bar → `01 queue · graph · 03 ledger` →
`04 telemetry · 05 analytics · 06 console`, with toasts, approval modal,
and the `07 audit` drawer. Clinical math is server-side (`data/rules.yaml` +
`data/hospital.yaml`); items marked DISPLAY are presentation mappings in
`public/app.js`. Live examples below are Campaign E + ambient.

## Top bar

| Element | Meaning |
|---|---|
| PULSE brand + facility block | Demo chrome (fictional St. Camillus Regional) |
| Facility pulse ECG + BPM | Canvas heartbeat; 72 nominal → 96 watch → 124 alert → 150 irregular at CODE DARK (DISPLAY ambience driven by max risk) |
| CODE badge | `NOMINAL` green · `WATCH` (max ≥12) · `ALERT` (≥25) · `CODE DARK` (≥35, red bar underline). Bands DISPLAY-fitted to our measured scale (campaign peak ≈41) |
| Clock | Wall-clock LIVE (scenario timestamps are synthetic, so no fake sim-clock) |
| AUDIT | Opens the audit drawer |

## Capability bar

- Left: `SCENARIO <id>` + caption narrating the running scenario (phase text), else the nominal prompt.
- Right: `EVT n · ALERTS n · INCIDENTS n` (open incidents) from `/api/stats`.

## 01 · Incident queue (ranked by clinical impact)

Each card: rank `#n`, `id · CONF %` (noisy-OR), title (DISPLAY from fired rules:
R1+R3 = ransomware, R10 = IoMT command, R5/R6 = credential abuse),
endpoint, **tier chips** (top 2 services), **budget countdown** (wall-clock burn of
`max_downtime_min`, `BUDGET BREACHED` at zero), confidence bar, and the big
**score + band** (`CRITICAL ≥38 · HIGH ≥30 · ELEVATED ≥12 · LOW`, DISPLAY bands).
Click selects → graph highlights, ledger loads. Contained incidents leave the queue.

## Graph (center)

- **Columns**: endpoints → applications → services (preset layout, fit on resize).
- **Colors**: workstation green-tint · server blue · IoMT amber · IoT gray ·
  application teal · services tier-bordered (T1 red / T2 amber / T3 gray).
- **Red dashed** = attack path (consecutive hops of the selected incident's path).
  **Amber dashed** = lateral-reach edges (server-computed segment reachability,
  `rel: reach` — only rendered for the highlighted incident).
- **Compromised** nodes pulse red; **contained** nodes go cyan; blast-radius mode
  dims everything off-path. Toggles: `BLAST RADIUS` (dim), `LATERAL REACH`
  (hide reach edges), `FIT`.
- Hover = tooltip (id, status); click endpoint = dossier (class, telemetry
  agent vs passive, status, incident link, dependency list); click canvas clears.
- Animated dashes + travelling packets are DISPLAY life (red on attack edges,
  teal on normal flows).

## 03 · Impact ledger (right detail)

1. Header: `id · OPENED hh:mm:ss · CONFIDENCE %`, title, endpoint + status.
2. `CONTAINMENT ACTIVE` banner when approved (residual note, stays reviewable).
3. **Explanation** — server-built narrative (rules, confidence, top service, path,
   fallback, deadline, Tier-1 instruction).
4. **Scorebox**: CLINICAL IMPACT (server `risk_score`) vs TECHNICAL SEVERITY
   (DISPLAY: rule-base × confidence) vs DIVERGENCE — the "don't rank by CVSS" slide.
5. **ATT&CK progression** chips light per fired rules (R5/R6/R10/R1+R3).
6. **Propagation path** steps (ORIGIN → RUNS → SUPPORTS) from the stored path.
7. **Services at risk** cards: tier, exposure (DIRECT / ×value / POTENTIAL LATERAL),
   fallback + readiness% + activation min, **FEASIBLE / INFEASIBLE-IN-BUDGET** tag
   (activation vs downtime — all server fields), live budget bars.
8. **Detected signals**: one row per rule (id, ATT&CK, evidence summary, time).
9. **Response**: recommendation box (auto vs needs-approval, clinical-notified flag)
   + pending actions with **OPEN APPROVAL** buttons + decided rows with approver.

## Approval modal

PULSE-styled, single-analyst truth: analyst toggle (A. Reyes, on shift) gates
CONFIRM; clinical chair row shows NOTIFIED (info only) when the recommendation
needs it. **Approve → incident `contained`** (leaves queue, feed greens, health
recovers, audited). **Deny** asks for a reason (audited, stays open). New events on
a contained endpoint open a fresh incident.

## 04 · Telemetry feed

Newest-first normalized events (`time endpoint TYPE summary`); rows on compromised
endpoints glow red; campaign phase narration (`details.note`) in purple.

## 05 · Analytics (`SEVERITY ≠ IMPACT`)

- **ALERTS / MIN**: SVG bars from `stats.alert_ts` (buckets over the data window,
  so synthetic timestamps still chart).
- **TECH vs CLINICAL scatter**: per-incident technical (DISPLAY) vs server score
  against the equality diagonal — points above the line are the whole argument.
- **ENDPOINT POSTURE**: per-class stacked bars (operational/watch/compromised/
  contained) from `stats.endpoint_status`.

## 06 · Demo console

Buttons A/B/C/D/**E** (reset + replay via API), **AMBIENT** (layers normal traffic,
no reset), **GUIDED DEMO** (D→A→B→C with pauses), **RESET** (wipes state, ledger
survives — append-only by design). Note: synthetic-only disclaimer.

## 07 · Response audit drawer

Full hash-chained ledger (`seq · actor · action · incident · time · prev→hash`).
**VERIFY CHAIN** recomputes server-side → green INTACT banner or red
`CHAIN BROKEN AT ENTRY #n`. **TAMPER (DEMO)** calls `POST /api/audit/tamper`
(demo-only endpoint that edits one stored payload) so judges see red live.
