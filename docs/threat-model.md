# Threat Model

## Assets

| Asset | Type | Criticality |
|---|---|---|
| Medication administration workflow | Service (T1) | Life-critical |
| Imaging reads (PACS) | Service (T2) | Urgent |
| Patient scheduling | Service (T3) | Deferrable |
| EHR / Pharmacy / LIS / PACS servers | Application | High |
| Infusion pumps, monitors, vents | Medical Device (IoMT) | Life-critical |
| AD, backup, file servers | Infrastructure | High |
| Workstations (nurse, radiology) | Endpoint | Medium |

## Adversary Capabilities

| Capability | Assumed | Notes |
|---|---|---|
| Phishing / credential theft | Yes | Shared logins on workstations |
| Vulnerability exploit (unpatched) | Yes | Legacy OS on devices, servers |
| Lateral movement (RDP/SMB) | Yes | Flat clinical VLAN in many hospitals |
| Device command injection | Yes | Default creds, no auth on HL7/proprietary |
| Ransomware deployment | Yes | Mass rename + recovery inhibition |
| Supply chain / vendor access | Yes | VPN jump host compromise |

## Attack Surface by Endpoint Class

```
Workstations  ──► phishing, shared creds, local ransomware
Servers       ──► RDP brute force, unpatched services, lateral pivot
VPN/Jump      ──► initial access, credential harvest
Backup        ──► recovery sabotage (R3)
IoMT Devices  ──► unauth commands, baseline deviation, pivot to clinical
IoT (cam/printer) ──► default creds, guest→clinical VLAN bridge
```

## Detection Coverage

| ATT&CK | Technique | Rules |
|---|---|---|
| T1486 | Data Encrypted for Impact | R1, R2 |
| T1490 | Inhibit System Recovery | R3 |
| T1110 | Brute Force | R5 |
| T1078 | Valid Accounts | R5 |
| T1021.001 | Remote Desktop Protocol | R6 |
| T1021.002 | SMB/Windows Admin Shares | R6 |
| T0855 | Unauthorized Device Command | R10 |
| — | Baseline Deviation (IoMT) | R9 |

## Gaps (Stretch / Future)

- T1059.001 PowerShell (R4) — encoded command detection
- T1021 Lateral burst (R7) — fan-out auth
- T1562.001 Impair Defenses (R8) — agent tampering
- T1048 Exfiltration (R12) — volume spike
- Cross-segment IoT→Clinical (R11) — network segmentation monitoring