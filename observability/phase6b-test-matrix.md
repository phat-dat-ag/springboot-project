# Phase6B acceptance matrix

Run`20261112T044156Z-a029b2`. Scope is isolated validation, not live activation.

Counts: `{"PASS": 19, "NOT VERIFIED": 10, "BLOCKED": 1}`. Earlier failed attempts are retained separately, not erased.

| Criterion | Status | Evidence / limit |
|---|---|---|
| Isolation/rendered and actual mounts | PASS | Internal network; no ports, existing stores, shared namespaces or live keys |
| Existing projects and volumes | PASS | IDs/start times/mounts preserved; all97 baseline volumes retained |
| Native TLS/mTLS and Grafana queries | PASS | Verified TLS1.3; rejection matrix; real OTLP/log ingestion and Grafana proxy queries |
| Real application SSL bundle / metrics proxies | NOT VERIFIED | Synthetic producer used; no three-API rebuild or five-proxy activation |
| OpenSearch certificate authentication/authorization | PASS | Separate admin, writer, reader; no demo users; restart and native restore |
| Positive password authentication / Dashboards | NOT VERIFIED | Incorrect credentials rejected; positive password/SSO/browser integration not exercised |
| Fluent Bit container SIGKILL recovery | PASS | 20/20 unique events in each real backend;0 missing/duplicates observed |
| Collector container SIGKILL recovery | PASS | 8/8 unique trace IDs; HTTP receiver success distinguished from durable admission |
| Host crash / storage failure durability | NOT VERIFIED | Memory-backed fixture and process-kill scope only |
| Bounded filesystem ENOSPC/recovery | PASS | 2MiB tmpfs only; explicit generated filler removed; fresh write succeeds |
| Output/trace queue overflow | PASS | Constrained Loki180/240 vs healthy OpenSearch240/240; Collector0/100 oversized-batch traces;2 fresh recovery traces |
| Backend disk-full corruption/recovery and pressure alerts | BLOCKED | No dedicated block device or filesystem-pressure exporter; incidental Prometheus snapshot ENOSPC observed separately |
| Grafana cold backup/restore | PASS | Same test login, API-created dashboard marker and lifecycle rule recovered |
| Loki cold backup/restore | PASS | 12 original control log IDs recovered in separate store |
| Tempo cold backup/restore | PASS | 3 control traces queried from separate restored store |
| Prometheus native snapshot/restore | PASS | Head included; historical instant-query samples match; checksummed file manifest |
| OpenSearch native snapshot/restore | PASS | SUCCESS snapshot restored into new secured cluster;12 control log IDs match |
| Off-host encrypted backup and operational RPO/RTO | NOT VERIFIED | Local disposable rehearsal only; no agreed production objectives |
| OpenSearch natural retention and physical deletion | PASS | New synthetic index; observed transition/delete,404 and UUID directory disappearance; no timestamp modification |
| Loki physical retention | NOT VERIFIED | 24h minimum fixture retention exceeds bounded window |
| Prometheus physical retention | NOT VERIFIED | 15m setting accepted; normal TSDB block lifecycle exceeds bounded window |
| Tempo end-to-end retention expiry | NOT VERIFIED | Old block directory removed but two cohort traces remained queryable in ingester/WAL; no full-expiry PASS |
| Actual alert lifecycle and no-data/error behavior | PASS | 10s evaluation/20s pending; observed inactive→pending→firing→inactive; exact NoData/Error states |
| Local notification grouping/retry/repeat/recovery | PASS | Two instances grouped; initial503 retried; firing/repeat/resolved received internally |
| Real external notification delivery | NOT VERIFIED | No external receiver, email or public webhook contacted |
| Bounded capacity/query measurements | PASS | 100 logs/20 traces; resource samples and native query latencies; no production extrapolation |
| Production load / browser rendering | NOT VERIFIED | No real API stress test or browser automation |
| Test credential leakage scan | PASS | Last1000 lines per fixture scanned; no global/historical guarantee |
| Safe stop and evidence retention | PASS | Exact labels/IDs; no volume-deleting cleanup; tmpfs volatility documented |
| Live production-security activation | NOT VERIFIED | Not authorized; existing deployment security FAIL remains OPEN |
