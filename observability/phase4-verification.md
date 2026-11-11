# Phase 4 verification — 2026-11-11

## A. Executive summary

Implemented and deployed to `springboot_project` with the existing debug override.
The three downstream-outage/restart recovery exercises passed, as did authenticated
Learning -> User tracing, fresh log/trace delivery and metrics regression. No
application source or Java configuration changed. No commits or pushes were made.
This is development pipeline hardening, not unconditional production acceptance:
disk-full/overflow, crash recovery, physical retention deletion and collection of
immediately compressed rotations during Fluent Bit downtime remain unverified.

Local sanitized evidence: ignored `phase4-baseline.log` and
`phase4-recovery-evidence.log`. Credentials remained in the existing ignored JSON
file and RAM; credential values, token values and user identifiers are omitted.

## B. Baseline findings

Read Compose/debug overrides, environment key names and protected fingerprints,
Fluent Bit/Loki/Collector/Tempo/Prometheus/Grafana configuration, application
rolling-file configuration and Phase 0–3 documentation before edits. All four
repositories started clean on develop. Snapshot UTC: 08:03:14.

Versions: Fluent Bit 3.2.10 (formerly floating tag 3.2, now exact tag), Loki 3.5.8,
OpenSearch 3.9.0, Collector Contrib 0.143.0, Tempo 2.9.0, Prometheus 3.13.5 and
Grafana 12.2.0. Existing versions otherwise unchanged.

Failure modes found: Fluent Bit memory-only chunks despite persistent offsets;
unlimited retries without disk budgets; Collector memory queue with 60s expiry;
unbounded Docker json-file logs; static OpenSearch application indices without ISM;
single-node replicas unassignable; Loki 4 GB WAL replay ceiling versus 512 MiB
container memory. Backend volumes and Loki/Tempo/Prometheus retention already
existed and were preserved. Docker filesystem snapshot: 65 GB used, 892 GB free,
7% utilization. OpenSearch data about 75 MB and vendor logs 18 MB; Prometheus data
about 25.5 MB at baseline. These are observations, not steady-state growth rates.

## C. Fluent Bit

Persistent full-sync/checksummed chunks and Full/WAL tail DBs share the existing
state volume. Sixteen chunks up, 16M backlog memory; per-output budgets 64M Loki
and 32M for each OpenSearch service. Retry backoff 1–10s, no attempt expiry;
oldest chunks for a full destination can be discarded. Logical budgets total
160M, not a filesystem quota. Independent output recovery was actually tested.
Fields and existing labels are preserved. Native dry-run accepted the config.

Isolated native Linux-volume tail fixture: five events survived rename, late old
inode write, new file, truncation and restart/current-file append without duplicate
replay; compressed history excluded and trace/span fields retained. Eight focused
assertions passed. Fixture `springboot_project-phase4-tail-8367439b65` stopped;
its volume and earlier stopped fixture attempts were retained. Initial fixture
permission/parser/Windows-bind assumptions failed and were corrected before the
native Linux fixture passed; no production application log was manipulated.

## D. Loki

Existing filesystem TSDB v13/24h schema, persistent volume and 720h retention
preserved. Compactor 10m, deletion delay 2h, workers reduced to four. WAL replay
128 MB and shutdown flush; ingestion/query bounds documented in logging-pipeline.md.
Native `-verify-config=true`, readiness, datasource queries, historical data and
post-outage synthetic delivery passed. Physical expired-data deletion NOT VERIFIED.

## E. OpenSearch

Single data node; initial three application replicas could not share a node with
their primary (`same_shard: NO`). Only the exact three legacy application indices
were safely adjusted to zero replicas. All six legacy/new application indices
are green; primaries are active. Final cluster is yellow solely because
`.opendistro-ism-config` and
`.opendistro-ism-managed-index-history-2026.11.11-1` retain unassigned system
replicas. Allocation explain confirmed the single-node reason. System settings
were not changed to force green.

New UTC event-date families preserve the `springboot-*-logs` wildcard and receive
cloned mappings, one primary, zero replicas and automatic 30-day ISM. Installer
uses supported APIs and three narrowly scoped templates; existing policy mismatch
fails rather than overwriting a different policy. Legacy UUIDs and nondecreasing
document counts were verified; they remain unmanaged indefinitely. No historical
indices deleted or retroactively attached. New policy attachment/mapping identity
passed. Numeric duration/status and trace/span/correlation fields remain searchable.
Retention savings concern future dated logs only, roughly limiting their active
age to 30 days plus ISM scheduling lag; no measured savings or deletion claim.

## F. Docker logging

Eleven main application/observability containers now have effective json-file
10m/3/compress=true configuration. Nominal combined 330 MiB before overhead,
excluding app files/backend/vendor files. Environment-configurable defaults in
`.env.example`. Databases, initializers and daemon settings unchanged. Existing
application file source is retained, with no second overlapping input. Recreated
containers' stdout is diagnostic storage, not a durable historical archive.

## G. Collector

Contrib 0.143.0 includes file_storage; native validation passed. New `otel_queue`
volume initialized to 10001:10001, root 0750, queue DB observed 0600. Same internal
OTLP HTTP receiver4318 and gRPC Tempo exporter4317. Persistent byte-sized 64 MiB
queue, two workers, fsync, compaction startup/rebound32/8 MiB; timeout5s and
retry1–10s without expiry. Overflow rejects new exports. Memory limiter and batch
remain. Final mounted config explicitly reloaded by Collector restart.

Observed queue DB 32,768 bytes while Tempo was stopped; all three traces survived
Collector restart while the destination remained down. Batch/application buffers
before queue admission are volatile. Queue payload capacity is not hard disk quota;
compaction needs extra disk. No exactly-once/crash/zero-loss claim.

## H. Tempo

2.9.0 existing persistent WAL/blocks, ownership, 72h retention and 5m maximum block
duration unchanged. Restart, readiness, old trace query and recovered new trace
queries passed through Grafana. Physical expiry deletion NOT VERIFIED.

## I. Prometheus

Existing volume, 15d/2GB retention, metric names/labels and histogram buckets
unchanged. Native promtool validation passed. All three targets UP. Full existing
metrics verifier passed HTTP/JVM/security/Hikari/histogram/private-endpoint checks.
Five exact historical sample series queried at their saved predeployment timestamp
remained identical after ordinary container recreation. Grafana datasource healthy.

## J. Capacity and security

Existing safe resource limits preserved: Fluent Bit256MiB/.5CPU, Loki512MiB/1,
OpenSearch2GiB/2 with512MiB heap, Prometheus512MiB/1, Collector256MiB/.5,
Tempo512MiB/1, Grafana512MiB/1. No new public ports; existing loopback bindings,
internal ingestion, secret mounts, private metrics and network boundaries preserved.
Twelve environment/key/credential fingerprints unchanged. Sampling remained 10%;
controlled probes used sampled W3C parents rather than changing environment policy.
No production TLS/authentication weakening was performed; existing local plaintext
and security-disabled OpenSearch remain development-only limitations.

## K. Automated tests and commands

Executed with the existing project/debug override:

```powershell
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml config --quiet
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml run --rm --no-deps fluent-bit /fluent-bit/bin/fluent-bit --dry-run -c /fluent-bit/etc/fluent-bit.conf
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml run --rm --no-deps otel-collector validate --config=/etc/otelcol/config.yml
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml run --rm --no-deps loki '-config.file=/etc/loki/loki-config.yml' '-verify-config=true'
docker compose -p springboot_project exec -T prometheus promtool check config /etc/prometheus/prometheus.yml
python observability/opensearch/configure-log-retention.py
python observability/verify-pipeline.py config
python observability/verify-pipeline.py health
python observability/verify-pipeline.py regression
python observability/verify-baseline.py --runtime
python observability/verify-metrics.py --credentials observability/local-test-credentials.json
```

Tempo config unchanged and validated by startup/readiness/query/restart, not a
claimed standalone configuration checker. Existing Maven suites executed with
`.\mvnw.cmd -o test` in each submodule: User102, Learning118, JWKS80; **300 tests,
zero failures, errors or skips**. No tests weakened. Metrics verifier query target
now includes dated indices. No Java files modified.

## L. Controlled runtime evidence

All tests sequential and synthetic. Original destination restored in finally.

| Destination outage | UTC start / duration | Evidence | Result |
| --- | --- | --- | --- |
| Loki | 08:33:19 / 61.32s | one FS chunk833B, retry observed, OpenSearch delivered while Loki down; Fluent Bit restarted before recovery; one completion per store | PASS |
| OpenSearch | 08:35:58 / 66.38s | one FS chunk840B, retry observed, Loki delivered while OpenSearch down; Fluent Bit restarted before recovery; one completion per store | PASS |
| Tempo | 08:37:37 / 36.28s | persisted queue DB32KiB; three traces queued, Collector restarted while Tempo down; logs continued, all traces recovered | PASS |

Observed trace IDs (not credentials):

- Loki recovery: `0843198135b24b9ca73c25e1e496058d`.
- OpenSearch recovery: `df7ae46022c1408b8e7e50799b555c1e`.
- Tempo recovery: `a83ca5f226754ffbb12243a098365998`,
  `55afb97f5fd24409bf4b5bfd837fba5e`, `52bf422ebcf74eb29bbc472ebaf237bb`.
- Historical Phase3 trace retained: `fda09edbe0bd47da8dee413d1fa31ec9`.

Authenticated login200, refresh200/rotation, internal JWT200, logout200 passed
using only the existing ignored test account. Actual distributed trace:
`5ccd3e5d5f904946b1887f69760d2063`;
independent correlation `phase4-auth-752d77a245014eaa`.

| Span | ID | Parent |
| --- | --- | --- |
| external sampled W3C parent | ffd5fa23db42464f | external |
| Learning server | f247f76f49af9251 | ffd5fa23db42464f |
| Learning client | b1682d4b9a1293b6 | f247f76f49af9251 |
| User server | dfdff7b2231ed531 | b1682d4b9a1293b6 |

Grafana Tempo query returned real spans; Loki/OpenSearch each had exactly two core
Learning/User completion records matching SDK span IDs, trace, correlation and200.
Actual credentials, session tokens and identity values plus JWT-shaped strings
were absent from inspected auth spans, matching backend logs and the bounded
application container-log window. This is observed-window evidence, not proof
against every possible sensitive input. Final health sweep08:58:41UTC passed
all APIs/backends/datasources, fresh trace and once-only logs; current Fluent Bit
process counters showed zero permanently failed retries and dropped records.

## M. Cross-project compatibility

JWKS public response bodies matched baseline, IDs/key contracts unchanged;
authenticated internal JWT communication passed. No application, key, endpoint or
header contract changes. `japanese-learning` requires no changes and was untouched.

## N. Acceptance matrix

| Criterion | Status | Scope |
| --- | --- | --- |
| Baseline inventory/config/volumes/protected hashes | PASS | before/after sanitized comparison |
| Filesystem buffering, bounded independent outputs | PASS | native config + two outage/restarts |
| Tail DB/restart/rename/truncate/compressed exclusion | PASS | isolated Linux-volume fixture |
| Rotation+compression during collector downtime | NOT VERIFIED | known unread archive loss window |
| Loki persistent storage/retention settings/limits | PASS | native validation + runtime |
| Loki physical expiry deletion | NOT VERIFIED | no historical deletion forced |
| OpenSearch replica investigation/narrow new-index ISM/mappings | PASS | application green; explained system yellow |
| OpenSearch physical expiry deletion | NOT VERIFIED | legacy intentionally unmanaged |
| Bounded effective Docker logging on11 main containers | PASS | runtime inspection |
| Persistent Collector queue/retry/restart recovery | PASS | three queued traces recovered |
| Queue overflow/disk-full/crash behavior | NOT VERIFIED | bounds configured, no destructive stress |
| Tempo persistence/retention/query/restart | PASS | historical and new traces |
| Tempo physical expiry deletion | NOT VERIFIED | short verification window |
| Prometheus persistence/targets/metrics/histograms | PASS | saved samples + full metrics verifier |
| Auth/JWT/JWKS/tracing/correlation/privacy regression | PASS | real existing-account traffic |
| Datasources/fresh logs/fresh traces/API health | PASS | final health sweep |
| Endpoint/security/key/env preservation | PASS | config + hashes + runtime checks |
| Maven regression | PASS | 300/0/0/0 |
| jp_dev/unrelated containers unchanged | PASS |16 jp_dev;21 unrelated baseline containers |
| Hard quotas/HA/backup-restore/production capacity | NOT VERIFIED | Phase6 acceptance |

## O. Git and container inventory

All three submodule branches/HEADs unchanged and worktrees clean. Root has only
the intended Compose/example-env/config/verification/documentation changes. No
commit, push, reset, branch switch or unrelated repository changes.

Eleven main containers recreated with existing images (no application build):
User, Learning, JWKS, Fluent Bit, Loki, OpenSearch, OpenSearch Dashboards,
Prometheus, Collector, Tempo and Grafana. New queue initializer/volume added.
An early `compose start tempo` reran its existing related storage initializer;
only StartedAt changed, with same container/image/mounts. Recovery helpers now
use exact `docker start` to avoid dependency reruns. Twenty-one unrelated baseline
containers, including all16 jp_dev containers, retained identity/start/mounts/ports.
Existing databases/volumes/keys were preserved; test fixture volumes retained.

## P. Remaining limits and follow-up

The requested normal downstream interruption/restart recovery checks passed.
Extended collector downtime across immediate compressed application rollover,
hard storage exhaustion, abrupt crashes, backup restore and actual retention
deletion remain explicit acceptance gaps; no claim of zero loss or exactly-once.
Legacy OpenSearch storage needs a separately reviewed archive/cleanup plan.
Resource budgets are development defaults, not measured production capacity.
Phase5 dashboards/alerts and Phase6 production acceptance were not implemented.
