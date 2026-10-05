# Detection Rules Reference

## MVP Rules (Implemented)

### R1 — Mass Rename/Modify Burst
**Signal**: >15 file_rename/file_modify events in 120s with extension flip to `.locked/.enc/.crypt/.ransom`
**ATT&CK**: T1486 Data Encrypted for Impact
**Weight**: 0.60 | **Severity**: high
**Applies to**: workstation, server

### R2 — Canary File Touched
**Signal**: Any write to configured canary paths
**Canaries**: `/shares/finance/__canary_do_not_touch.txt`, `C:\canary\patient_list_decoy.xlsx`, `/pacs/__canary.dcm`
**ATT&CK**: T1486
**Weight**: 0.80 | **Severity**: critical

### R3 — Recovery Inhibition
**Signal**: Process commandline matches `vssadmin|wbadmin|bcdedit|del.*backup|rm.*backup|vss.*delete|shadow.*delete|wipe.*catalog` OR backup_job action in `delete_catalog|wipe_repo|disable_job`
**ATT&CK**: T1490 Inhibit System Recovery
**Weight**: 0.70 | **Severity**: high

### R5 — Brute Force Then Success
**Signal**: ≥5 failed logons then success for same user within 10 minutes
**ATT&CK**: T1110 Brute Force / T1078 Valid Accounts
**Weight**: 0.55 | **Severity**: medium

### R6 — New RDP/SMB Source
**Signal**: RDP or SMB logon from source IP not in server's allow-list
**Allow-lists** (per server): defined in `rules.yaml`
**ATT&CK**: T1021.001 RDP / T1021.002 SMB
**Weight**: 0.60 | **Severity**: high

### R9 — Device Baseline Deviation
**Signal**: net_flow or device_command to dst/port/proto not in device's learned baseline
**Baselines** (per device): defined in `rules.yaml` (e.g., pump→10.10.20.5:8443/tcp)
**ATT&CK**: baseline (custom)
**Weight**: 0.65 | **Severity**: high
**Applies to**: device, iot

### R10 — Unauthorized Device Command
**Signal**: device_command from source not in allow-list OR config command (dose_rate, set_config, firmware_update, reboot) outside maintenance window (02:00–04:00)
**Allow-lists** (per device): defined in `rules.yaml`
**ATT&CK**: T0855 Unauthorized Device Command (ICS)
**Weight**: 0.85 | **Severity**: critical
**Applies to**: device

## Stretch Rules (Not Implemented)

| ID | Rule | Signal | ATT&CK |
|---|---|---|---|
| R4 | Suspicious script launch | Encoded PowerShell from browser/Office | T1059.001 |
| R7 | Lateral burst | One host authenticating to >4 hosts in 10m | T1021 |
| R8 | Security tool tampering | Endpoint agent/AV stopped | T1562.001 |
| R11 | Cross-segment flow | IoT device talking into clinical VLAN | Lateral movement |
| R12 | Outbound volume spike | Z-score vs baseline | T1048 Exfiltration |

## Correlator

- Groups alerts on same `endpoint_id` within 30-minute sliding window
- **Confidence** = noisy-OR of rule weights: `1 - ∏(1 - w_i)`
- Example: R1(0.6) + R2(0.8) + R3(0.7) = 1 - 0.4×0.2×0.3 = **0.976**
- Creates single `Incident` with aggregated `rule_ids`, `alert_count`, `confidence`

## Configuration

All thresholds, weights, allow-lists, baselines in `data/rules.yaml` — editable without code changes.