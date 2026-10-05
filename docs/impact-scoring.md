# Impact Scoring

## Formula

```
exposure =
  1.0  if service runs directly on compromised endpoint (path length ≤ 3)
  0.6  if service depends on an application on the endpoint (dependency)
  0.3  if service is reachable via lateral segment pivot (potential)

tier_weight:  T1=1.0 (life-critical), T2=0.6 (urgent), T3=0.3 (deferrable)
fallback_readiness: from hospital.yaml (0.0–1.0)

service_risk = tier_weight × (1 − fallback_readiness) × exposure × detection_confidence

incident_risk = min(100, max(service_risk) × 100 + 0.1 × sum(other_service_risks) × 100)
```

## Example: Scenario A (Radiology Workstation)

- Compromised: `rad-ws-02` (workstation)
- Rules fired: R1, R2, R3, R5, R6 → confidence ≈ 0.976
- Direct path: `rad-ws-02 → pacs_viewer → pacs → imaging_reads` (T2)
- `tier_weight=0.6`, `fallback_readiness=0.5`, `exposure=0.6` (dependency, path len 4)
- `service_risk = 0.6 × 0.5 × 0.6 × 0.976 = 0.176`
- `incident_risk = 17.6` → **Medium-High**

## Example: Scenario B (Pharmacy Server)

- Compromised: `pharm-srv-01` (server)
- Same rules → same confidence ≈ 0.976
- Direct path: `pharm-srv-01 → pharmacy → medication_administration` (T1, path len 3)
- `tier_weight=1.0`, `fallback_readiness=0.6`, `exposure=1.0` (direct)
- `service_risk = 1.0 × 0.4 × 1.0 × 0.976 = 0.390`
- `incident_risk = 39.0` → **Critical** (Tier-1, 15-min deadline)

## Example: Scenario C (Infusion Pump)

- Compromised: `pump-icu-04` (device)
- Rules fired: R9, R10 → confidence ≈ 0.98
- Path: `pump-icu-04 → infusion_mgmt → medication_administration` (T1)
- But device class = "device" → playbook forces **passive-only**
- Risk scored but **never auto-contained**

## Fallback Readiness Impact

| Service | Fallback | Readiness | (1-readiness) | Effect on Risk |
|---|---|---|---|---|
| medication_administration | Paper MAR | 0.6 | 0.4 | moderate |
| imaging_reads | Local DICOM viewer | 0.5 | 0.5 | higher |
| patient_scheduling | Phone booking | 0.9 | 0.1 | low |

Lower readiness → higher risk → earlier fallback activation recommended.

## Deadline Clock

Dashboard shows `max_downtime_min` countdown for top service:
- T1 (medication): 15 min
- T2 (imaging): 120 min
- T3 (scheduling): 480 min

## Output per Incident

- `risk_score` (0–100)
- `services_at_risk[]` with service, tier, exposure, risk, path, fallback, deadline
- `paths[][]` for graph highlighting
- `explanation` — plain-English narrative for panel