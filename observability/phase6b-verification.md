# Phase6B verification — 2026-11-12

## A. Executive summary

Implemented and executed the dedicated `springboot_phase6b` laboratory. Safe selected tests are complete, with explicit remaining gates. **Full Phase6B acceptance and overall production readiness are not established.** Native security, process-crash recovery, bounded queue overflow, five-store restore rehearsals, elapsed alert lifecycle and local notifications were exercised. Live production telemetry security remains FAIL/OPEN: the existing deployment was not migrated or restarted.

Final acceptance matrix counts: `{"PASS": 19, "NOT VERIFIED": 10, "BLOCKED": 1}`. These are scoped criteria, not an extension of the historical795-check score. Full attempt history counts: `{"PASS": 275, "FAIL": 21, "NOT VERIFIED": 12, "BLOCKED": 2}`. Unsuccessful harness/native-startup/sizing attempts remain in ignored evidence; the matrix uses later verified observations without deleting history. No commit, push, branch switch, existing-volume deletion, live key regeneration or external notification occurred.

## B. Isolation and baseline

Run`20261112T044156Z-a029b2`; evidence`data/phase6b/20261112T044156Z-a029b2/evidence/`. Baseline captured41 containers (18 target,16`jp_dev`,7 prior stopped fixtures),97 existing volumes and12 networks before new Docker resources. This includes all93 original roadmap volumes. All remained intact. One new internal network and15 uniquely named tmpfs-backed volumes have per-run labels. No host ports, external networks, application databases or inherited Compose services were used.

The rendered model and actual mounts/networks/ports were audited. Only run-local read-only config/PKI binds and a writable run-local evidence directory are allowed. Exact project/run labels guard every stop/SIGKILL/start; cleanup validates each exact resource name. `probe` is a test-only orchestrator and volume anchor, never a production component. All actors have CPU/memory/swap/PID/log limits. Stores are explicitly size-limited, source generation capped4MiB/suite, physical fill restricted to2MiB tmpfs, host memory abort floor2GiB. Resource observations are in`resources-*.json`.

All data stores are memory-backed: the anchor retains mounts across backend-process stops, but this does not model host failure or durable disk. Evidence and backup artifacts were copied to the ignored run directory before shutdown. Production/development PKI and accounts were never imported into the lab.

## C. TLS/mTLS

Native Loki, Tempo, Collector, Prometheus and Grafana negotiated TLS1.3/`TLS_AES_128_GCM_SHA256` in recorded probes. Verified trusted clients succeed; missing/untrusted client certificates are rejected by mTLS endpoints; wrong CA and hostname tests reject connections. Native HTTPS scrapes have four targets. Real fixture OTLP→Collector→Tempo delivery and Grafana trace resolution passed; Fluent Bit sent logs to actual secure Loki/OpenSearch. Grafana datasource TLS queries passed; its Tempo plugin lacks a health method, so actual proxy/trace requests were used.

Disposable CA/leaf certificates include explicit constraints, key usage, SANs and EKUs. Python3.14 initially rejected an underspecified test CA; it was corrected without disabling verification. A second authorized client leaf was accepted under the same CA. Server hot reload, root-CA rollover, revocation, real Spring SSL-bundle images and the five production metrics proxies remain NOT VERIFIED. Fixture control/local notifications and native Collector/Fluent Bit metrics use private test-network HTTP, explicitly not a claim of full production-profile security.

## D. OpenSearch security

OpenSearch3.9.0 initialized through native`securityadmin.sh`, with hostname/CA checks enabled, a distinct admin certificate and vendor reserved role definitions. No demo users/passwords were copied. The writer can create/bulk-ingest the three dated application-index families but cannot search or write unrelated indices. Reader cannot write or access security administration. Missing/untrusted certificates and unmapped/incorrect credentials are rejected (TLS failure or401/403 as appropriate). Restart and restored-cluster queries retained security and data.

Authentication was positive certificate authentication, not positive password authentication. Trusted but unmapped certificates can authenticate and then receive403; this is not incorrectly described as a401 password test. Dashboards/SSO/password integration remains NOT VERIFIED. Synthetic secured snapshot restore rehearsed data migration only; no unsecured-live-to-secured migration was attempted. The separate approval-gated live migration procedure in[secure-production/README.md](secure-production/README.md) still applies.

## E. Crash durability

Only exact fixture processes were killed. Fluent Bit SIGKILL recovered20 submitted log events in each backend:20 unique,0 missing,0 observed duplicates. Collector SIGKILL recovered8/8 trace IDs after backend outage; backend Loki crash plus queued input recovered10/10 IDs. Tail DB and chunks/queue mounts were retained. HTTP200 from the OTLP receiver is not a durable-queue/backend acknowledgement. Tempo trace-ID queries do not prove absence of physical duplicate spans. Container SIGKILL is not host-crash/storage-failure proof; exactly-once delivery is not claimed.

## F. Disk-full and overflow

A dedicated2MiB tmpfs returned ENOSPC at its capacity; removal of only the generated filler restored writes. No host filesystem was filled. In the completed multi-chunk output test, constrained Loki stored180/240 unique events (60 missing), while an independently budgeted healthy OpenSearch output stored240/240. Later reconciliation confirmed those counts. No duplicates were observed in that cohort. Initial equal64KiB destination budgets also lost records at the available destination; it was given its own1MiB fixture budget and the observation was retained. A single oversize chunk did not exercise eviction, so the final test used paced chunks.

Collector's16KiB queue rejected an oversized100-span batch during outage: receiver HTTP200,0 queryable traces after recovery, enqueue-failure metrics recorded. Two fresh recovery traces succeeded. These tests establish lossy overflow boundaries, not unlimited recovery. Backend corruption/recovery under a dedicated full disk and reliable disk-pressure alert coverage remain BLOCKED. Separately, native Prometheus snapshot preallocation returned ENOSPC on its bounded128MiB fixture store; supported16MiB segment flags allowed a successful snapshot at the same capacity.

## G. Backup and restore

All five stores restored synthetic data into separate disposable targets. Loki/Tempo/Grafana used quiesced full-store copies with SHA256 artifacts:12 log controls,3 trace controls, and the test login/API-created dashboard/lifecycle rule respectively. Approximate cold-copy workflow durations (including stop/start/query overhead) are42s Loki,41s Tempo and8s Grafana; manifests retain exact UTCs.

Prometheus native snapshot included head, produced a checksummed file manifest and matched historical instant-query values after restore. OpenSearch native snapshot returned SUCCESS; a fresh security-initialized clone restored12 control log IDs, with source OpenSearch stopped while the restore used the shared *fixture-only* repository read-only. Security-index/global-state restore was deliberately excluded. Native backup resumed after the initial Prometheus preallocation failure; successful cold restores were not overwritten.

These are local synthetic restore rehearsals. Off-host encrypted storage, production credentials/configuration recovery, agreed RPO/RTO and live operational restore remain NOT VERIFIED. Forensic hot source/queue/repository copies collected at shutdown are not promoted to consistent backup evidence.

## H. Retention

OpenSearch's new exact-target synthetic index naturally progressed through ISM and deleted: index404 plus previously observed UUID shard directory disappearance with no traversal errors. No live policy/index or creation timestamp changed. Loki accepted24h retention but expiry exceeds the bounded window. Prometheus accepted15m retention but normal head/block lifecycle exceeds the window. Tempo removed an old physical block directory under30s fixture retention, but both cohort traces remained queryable through ingester/WAL state; complete end-to-end expiry remains NOT VERIFIED. Fresh control traces still worked. All live retention settings remain unchanged.

## I–J. Grafana lifecycle and local notifications

Observed10s evaluations/20s pending: inactive at07:04:21.932UTC, pending07:04:32.440, firing07:04:50.866, recovered inactive07:05:52.740. Polling timestamps have scheduler/query tolerance; the state API stores evaluations/instance detail. Two instances grouped into a local payload. The first receiver attempt returned503; retry, repeat and resolved delivery were observed. Separate missing-series and invalid-PromQL rules produced exact NoData and Error instance states. An initial verifier looked for the wrong no-data spelling; actual instance assertions were corrected and rechecked without replaying the elapsed test.

Only the internal local receiver was configured. Existing21 rules, contacts, policies and mutes were untouched. Real external email/webhook delivery remains NOT VERIFIED. Local success cannot establish external provider readiness.

## K. Performance and capacity

100 synthetic logs and20 traces were queryable. The nominal ceiling was10logs/s for10sec, with serial Docker/probe overhead reducing actual offered throughput. End-to-end generation/drain/query workflow took38.264s: observed2.61logs/s including that overhead. This is an observed small-fixture result, not maximum sustainable throughput. Native HTTP samples were16.99–66.63ms Loki,17.55–96.41ms Prometheus and15.29–94.28ms Grafana datasource proxy (three serial samples each). Docker-wrapper OpenSearch samples were877–1365ms and are explicitly not backend-only timings. CPU/memory, allocated storage, queue/buffer counters and before/after resources were recorded. No production capacity or browser dashboard latency claim follows.

## L. Regression and preservation

Every suite compared immutable original IDs/start times/mount identities/networks and retained97 baseline volumes. Docker mount-list ordering was normalized after an initial false difference; the original baseline was not rewritten. Existing16`jp_dev` containers,18 target containers and prior fixtures remained unchanged. Grafana datasource/dashboard/rule/contact/policy fingerprints and nine UP targets were rechecked. The separate remediation preservation verifier confirms historical logs/traces/Prometheus samples, OpenSearch index UUIDs/counts, keys/env fingerprints and JWKS responses. No recovery/restart of unavailable development endpoints was attempted. No application/submodule source changed in Phase6B; prior309 Java tests remain historical evidence, not a newly rerun suite.14 new Python safety/CI tests passed.

## M. Commands, results and evidence

Executed`prepare`, rendered`validate`, isolated`start`, selected`test --suite security|opensearch|crash|overflow|lifecycle|performance|backup|backup-native|retention`,`preserve`,`collect`, and exact-ID`stop`. Every attempt records command, UTC start/end, duration, expected/actual result and evidence directory. Early one-off repair/revalidation commands are described above; failed attempts are not silently removed. Final source returns1 for failed checks and2 for BLOCKED/NOT VERIFIED evidence. [Acceptance matrix](phase6b-test-matrix.md) and[sanitized measurements](phase6b-measurements.json) separate scoped final criteria from raw attempt counts.

## N. Remaining production gaps

Live telemetry authentication/TLS migration, real application/proxy and password/Dashboards validation, server/CA rotation, full host/storage durability, dedicated backend disk-full/pressure alerts, complete Loki/Tempo/Prometheus expiry, off-host recovery, external notifications, browser interaction and representative capacity remain open. Security validation in this lab does not change the deployed security FAIL to PASS.

## O. Git changes

Phase6B adds`observability/phase6b/` harness/probe/suites/safety tests/report renderer/environment example/README, this report, test matrix and sanitized measurements. Dated follow-ups append to production-readiness, telemetry-security, backup-restore, operations-runbook and observability README. All pre-existing uncommitted Phase6A/remediation files are retained. Root/submodule branches and HEADs are unchanged; module worktrees match the captured baseline. Full final modified/untracked inventory is in ignored`final-git.json`. No commit/push or unrelated-repository modification occurred; `japanese-learning` requires no changes.

## P. Cleanup and evidence retention

Fixture containers were stopped only after evidence collection. No Phase6B volume/network/container definition was deleted automatically. Memory-backed contents can disappear on final unmount; checksummed backup/forensic artifacts, logs, manifests, measurements and PKI remain under ignored run data. The supplied cleanup requires`--confirm <exact-run-id>` and validates each resource label, retaining host evidence. Volume-deleting cleanup was not executed. Final original-project preservation was verified again after stop.

## Q. Recommendation

Accept the executed isolated evidence with the explicit NOT VERIFIED/BLOCKED gates. Do not declare complete Phase6B acceptance or production readiness. Review the results, then separately authorize any live secure migration or dedicated-host storage/performance work. External delivery needs its own authorized destination test. No further tests or activation are implied by this report.
