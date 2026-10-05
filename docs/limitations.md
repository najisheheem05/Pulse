# Limitations & Assumptions

## 1. "Patient Harm" Is a Proxy

The platform measures **service impact**, not direct patient harm. Criticality tiers (T1/T2/T3), maximum downtime windows, and fallback readiness values are **hand-assigned assumptions** that clinicians must validate. A T1 service with 60% fallback readiness may still cause harm if fallback activation takes 20 minutes but the clinical window is 15.

## 2. Circular Detection Validation

Both the **simulator** (event generator) and **detection rules** are authored by the same team. There are **no real-world accuracy figures** (precision/recall/F1) — this is a proof-of-concept demonstrating the *architecture* of clinical-impact ranking, not a validated detector.

## 3. Synthetic Baselines Only

Device baselines (R9) are learned from the **same synthetic "normal" traffic** used in scenarios. No real Zeek/NetFlow data, no long-term profiling, no concept drift handling.

## 4. Simulated Agent Telemetry

Workstation/server events are **synthetic JSON** matching a Sysmon-like schema. Real deployment requires:
- Sysmon / Windows Event Forwarding / EDR agent deployment
- Passive network sensor (Zeek, Suricata) on SPAN/TAP for IoMT/IoT
- Protocol parsers for HL7, DICOM, proprietary medical protocols

## 5. No Encryption/Ransomware Code

The simulator **only emits synthetic JSON events**. It does not execute real encryption, ransomware, or destructive commands. This is by design — the detector consumes events, not binaries.

## 6. Single-Analyst Approval (Demo Scope)

The approval flow implements **single analyst approve/deny** for hackathon velocity. Production would require:
- Dual approval (analyst + clinical) for Tier-1
- Maintenance window enforcement for device segmentation changes
- RBAC and approval delegation

## 7. Graph Is Static

The hospital dependency graph is loaded from YAML at startup. No dynamic discovery of:
- New endpoints joining the network
- Application topology changes
- Segment reconfiguration

## 8. No Multi-Tenant / Multi-Hospital

Single hospital model, single database. No isolation between facilities.

## 9. SQLite Concurrency

`sqlite3` (stdlib) handles demo load but is **not production-ready** for concurrent writers. Would need PostgreSQL + connection pooling.

## 10. Time Synchronization Assumed

All timestamps assumed UTC and synchronized. No handling of clock skew between endpoints, sensors, and server.