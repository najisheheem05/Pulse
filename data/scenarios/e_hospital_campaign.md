# Campaign E — "After-Hours Affiliate" (narrated kill chain)

File: `data/scenarios/e_hospital_campaign.json` (64 synthetic events, no malware —
the detector only consumes JSON). Rebuild: `python3 scripts/make_campaign.py`.
Run: `make demo SCENARIO=e` or dashboard **E Campaign** button.

## Why this story is plausible

Real hospital ransomware (Ryuk/Conti/BlackCat affiliates, 2019–2024) follows
exactly this shape: **stolen vendor VPN creds → night-shift workstation →
unpatched file/AD servers → pharmacy/EHR crown jewels → recovery sabotage**,
with IoMT touched opportunistically because clinical VLANs are flat and device
credentials are default. Every phase below maps to an implemented rule.

## Phase table (presenter script, ~90 seconds)

| Clock | Phase | What happens | Rule | What judges see |
|---|---|---|---|---|
| 02:10 | P0 ambient | Night shift: nurse logon, PACS read, pump/monitor heartbeats | — | Event ticker alive, **0 incidents** — the hospital at work |
| 02:14 | P1 initial access | 6 failed + 1 successful vendor VPN logon from `203.0.113.9` | **R5** brute-force→success (T1110) | `vpn-jump-01` incident — the way in |
| 02:21 | P2 execution | 18 files → `.locked` on `nurse-ws-01`, finance canary tripped, `vssadmin delete shadows` | **R1+R2+R3** (T1486/T1490) | Workstation incident, noisy-OR confidence ≈0.99 |
| 02:33 | P3 lateral | Same vendor session hits `filesrv-01`, `ad-01`, `pharm-srv-01` from unknown internal sources | **R6** ×3 (T1021) | Three RDP/SMB incidents — the graph fans out from one session |
| 02:36 | P4 crown jewels | Same playbook on `pharm-srv-01` + `wbadmin delete catalog` | **R1+R2+R3** | **Top-ranked: medication_administration T1, 15-min clock, Paper MAR** |
| 02:47 | P5 IoMT pivot | Lobby camera scans clinical VLAN; pump talks back on telnet; rogue `dose_rate` + `rate_limit=off` from camera subnet | **R9+R10** (T0855) | Pump incident, **passive-only, approval required** — never auto-isolated |
| 02:55 | P6 recovery kill | `backup-srv-01` catalog deleted | **R3** (T1490) | Backup incident — restores would fail; this is why P4 is unsurvivable without the fallback |
| 02:58 | Tail | Ventilator heartbeat + doctor logon continue | — | The hospital keeps breathing through the attack |

## Expected ranked output (8 incidents, 1 endpoint each)

1. `pharm-srv-01` ≈ 40.6 — medication_administration **T1** (isolate needs approval)
2. `nurse-ws-01` ≈ 40.2 — medication_administration T1 via EHR client (same behavior, ranked by its own path — compare with A/B)
3. `pump-icu-04` ≈ 38.8 — medication_administration **T1** (passive monitoring only)
4. `backup-srv-01` ≈ 30 — all three services (recovery for everything is gone)
5. `ad-01`, `vpn-jump-01` — entry + privilege-staging trail
6. `cam-lobby-01`, `filesrv-01` — compromised camera scanning clinical (bonus R9), first-hop file server

Talking point: *"One vendor password. Forty-eight minutes. Pharmacy, pumps, and
backups — ranked not by malware severity but by what each endpoint can take
away from patients."*
