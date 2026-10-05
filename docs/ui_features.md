# UI Features — every control in the PULSE console and how to use it

Console: http://localhost:8000. This guide covers **behavior** (click this → that
happens). For what the numbers and colors *mean*, see `docs/site_outputs.md`.

## Top bar

| Feature | How to use | What happens |
|---|---|---|
| Facility pulse (ECG + BPM) | Passive — just watch it | Heartbeat animates continuously; BPM steps 72 → 96 → 124 → 150 (irregular trace) as the facility CODE escalates with max risk |
| CODE badge | Passive indicator | `NOMINAL` → `WATCH` → `ALERT` → `CODE DARK` as the highest open risk crosses 12 / 25 / 35; CODE DARK underlines the whole bar red and fires a toast |
| Clock | Passive | Wall-clock time + LIVE tag (scenario timestamps are synthetic, so the console makes no sim-time claims) |
| AUDIT button | Click | Slides in the Response Audit drawer (07) over the right side |

## Capability bar

| Feature | How to use | What happens |
|---|---|---|
| Scenario caption | Appears automatically while a scenario runs | Shows `SCENARIO <id>` + a narrating caption that advances mid-run (e.g. campaign P1→P6); returns to the nominal prompt when done |
| EVT · ALERTS · INCIDENTS | Passive counters (1 s poll) | Total ingested events, total alerts, open incidents |

## 01 · Incident queue

| Feature | How to use | What happens |
|---|---|---|
| Ranked cards | Read top-down — rank is clinical impact, not alert volume | Sorted by `risk_score`; band color follows the top service tier (red T1 / amber T2 / green T3) |
| Budget countdown | Watch the `budget m:ss` chip | Live wall-clock burn of the top service's `max_downtime_min`; flips to `BUDGET BREACHED` at zero |
| Select incident | Click any card | Graph highlights its attack path red; the Impact Ledger (03) loads; card gets the selected outline |
| Toasts | Automatic | A toast fires when a *new* incident appears while you watch (title + endpoint + score) |

## Dependency graph

| Feature | How to use | What happens |
|---|---|---|
| Layered map | Pan (drag), zoom (wheel) | Endpoints → applications → services, left to right; auto-fits on window resize |
| Legend (header) | Hover for the key | Workstation / server / IoMT / IoT colors, Tier 1-2 borders, red = attack path, amber = at-risk reach |
| Attack path | Select an incident | Its stored propagation hops render red-dashed with animated flow; everything off-path dims (blast-radius mode) |
| Lateral reach | Select an incident | Server-computed pivot edges render amber-dashed into services reachable by VLAN, without a confirmed compromise |
| BLAST RADIUS toggle | Click | Toggles the dimming of off-path nodes — full hospital context vs focused blast view |
| LATERAL REACH toggle | Click | Shows/hides the amber reach edges |
| FIT | Click | Re-fits the whole graph to the panel |
| Node hover | Hover any node | Tooltip with node id + live status (operational / compromised / contained) |
| Endpoint dossier | Click any node | Ledger switches to a dossier: class, agent-vs-passive telemetry, status, linked incident, full dependency list; click canvas background to clear |
| Contained nodes | After approval | Compromised red pulse becomes a steady cyan outline; its edges render cut (dimmed) |
| Ambient life | Passive | Teal packets drift along normal dependency edges even with no attack running |

## 03 · Impact ledger

| Feature | How to use | What happens |
|---|---|---|
| Header | Read | `id · OPENED time · CONFIDENCE %`, auto-titled by fired rules, endpoint + open/contained status |
| Explanation | Read | Server-built plain-English narrative: rules, confidence, top service, path, fallback, deadline, Tier-1 instruction |
| Scorebox | Read/compare | CLINICAL IMPACT (server) vs TECHNICAL SEVERITY (display estimate) vs DIVERGENCE — the "don't rank by CVSS" argument in three numbers |
| ATT&CK progression | Read | Four tactic chips (Credential Access / Lateral Movement / C2 / Impact) light up per fired rules |
| Propagation path | Read top-down | ORIGIN (compromised) → RUNS (hosts app) → SUPPORTS (clinical service) steps from the stored path |
| Service cards | Read + watch | Per-service risk, exposure (DIRECT / ×factor / POTENTIAL LATERAL), fallback + readiness + activation, FEASIBLE / INFEASIBLE-IN-BUDGET tag, live budget bar |
| Detected signals | Read | One row per fired rule: id, ATT&CK, evidence summary, time |
| Response box | Read | The playbook recommendation (auto-executed vs needs-approval, clinical-notified flag) |
| OPEN APPROVAL | Click per pending action | Opens the approval modal (below) |
| Decided rows | Read | Approved/denied actions stay listed with decider — the audit trail at a glance |

## Approval modal

| Feature | How to use | What happens |
|---|---|---|
| Analyst toggle | Click APPROVE once | Arms CONFIRM EXECUTION (single-analyst authority: A. Reyes, on shift) |
| Clinical row | Read-only when present | Shows the clinical chair as NOTIFIED for Tier-1 (information, not a second gate — matches the single-approval backend) |
| CONFIRM EXECUTION | Click when armed | Approves via API → incident becomes `contained`, leaves the queue, feed greens, health recovers, toast confirms; both decision and containment are hash-chained |
| DENY | Click, enter a reason | Records denial + reason, incident stays open for re-review |
| CANCEL | Click or backdrop | Closes with no effect (nothing is ever auto-executed) |

## 04 · Telemetry feed

| Feature | How to use | What happens |
|---|---|---|
| Live stream | Watch newest-first | Every ingested event as `time endpoint TYPE summary`; rows on compromised endpoints glow red; campaign phase narration (`P1…P6`) renders purple |
| Hover any row | Hover | Full summary in the tooltip |

## 05 · Analytics

| Feature | How to use | What happens |
|---|---|---|
| ALERTS / MIN | Watch during replays | Red bars spike as rules fire (bucketed over the data window, so synthetic timestamps still chart) |
| TECH vs CLINICAL scatter | Read per incident | Points above the equality diagonal are incidents the CVSS-style view would under-rank — the product thesis as a chart |
| ENDPOINT POSTURE | Read per class | Stacked operational / watch / compromised / contained bars for workstations, servers, IoMT, IoT |

## 06 · Demo console

| Feature | How to use | What happens |
|---|---|---|
| D BENIGN | Click | Resets, replays patching/backup noise → expect 0 incidents (honest negative) |
| A RADIOLOGY | Click | Resets, radiology ransomware → ≈31, imaging T2 |
| B PHARMACY | Click | Resets, same playbook on pharmacy server → ≈40.6, medication T1, 15-min clock |
| C ROGUE PUMP | Click | Resets, rogue pump commands → ≈38.8, T1, passive-only response |
| E CAMPAIGN | Click | Resets, 64-event connected kill chain → 8 incidents, pharmacy + pump T1 on top |
| AMBIENT | Click (no reset) | Layers ~15 min of normal traffic onto current state — feed comes alive, fires nothing |
| GUIDED DEMO | Click | Runs D → A → B → C automatically with pauses (then suggests E) |
| RESET | Click | Wipes events/alerts/incidents/actions (audit ledger survives — append-only by design) |
| Running state | While active | Button shows running, other scenarios disable, caption narrates; RESET cancels mid-run |

## 07 · Response audit drawer

| Feature | How to use | What happens |
|---|---|---|
| Ledger list | Open via AUDIT, scroll | Every entry: `seq · actor · action · incident · time · prev-hash → hash` (detections, upserts, approvals, denials, resets) |
| VERIFY CHAIN | Click | Server recomputes every link → green INTACT banner (`N entries verified`) or red `CHAIN BROKEN AT ENTRY #n` |
| TAMPER (DEMO) | Click, then VERIFY | Corrupts one stored payload via the demo-only endpoint so judges watch the badge flip red live |
| CLOSE ✕ | Click | Slides the drawer away (polling continues underneath) |

## Toasts

Bottom-right transient notifications: scenario start/complete, new incidents,
CODE escalations, approval/denial confirmations, tamper + reset notices.
Informational only — they never block input and expire after ~5 s.
