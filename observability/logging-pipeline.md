# Logging pipeline reliability (Phase 4)

Logback JSON console and rolling files remain unchanged. Fluent Bit 3.2.10 tails
the three exact current application files, preserving JSON types, service metadata,
traceId, spanId and correlationId. Independent outputs send to Loki 3.5.8 and
OpenSearch 3.9.0. This is not an OTLP logs pipeline.

## Persistent collection and backpressure

`fluent_bit_state` holds the existing tail SQLite databases and new `buffer/`
filesystem chunks. Tail DB sync is Full with WAL; chunk sync is full with checksums.
Sixteen memory-resident chunks (roughly 32 MiB, not a hard memory ceiling), a
16 MiB startup backlog memory budget and the existing 256 MiB container limit
bound ordinary memory use. Input lines over 256 KiB are skipped rather than
blocking a whole file. No unlimited line-size support is claimed.

Retries have no attempt expiry, with scheduler backoff 1–10 seconds. They are
paired with bounded logical output storage: Loki 64M, each of three OpenSearch
outputs 32M, configurable using `FLUENT_BIT_LOKI_BUFFER_LIMIT` and
`FLUENT_BIT_OPENSEARCH_BUFFER_LIMIT`. Nominal combined destination budget is 160M;
shared chunks, DB/WAL, metadata and temporary overhead mean this is not a volume
quota. At a destination's limit Fluent Bit discards its oldest queued chunks to
admit new ones. A failed destination does not intentionally block the other.
Disk-full loss and queue-overflow ordering were not stress-tested.

The internal HTTP monitor on 2020 exposes storage/retry counters to trusted Docker
services only; no host port or second Prometheus scrape pipeline was added.
Grace is 30s, Compose stop grace 40s. Existing DB identities are retained.

## Rotation and restart scope

Inputs match only `user-api.log`, `learning-api.log`, `jwks-api.log`, never archives.
`Read_from_Head On` applies to previously unknown files; persisted DB offsets avoid
replaying known files after normal restart. Rotate_Wait is 30s. Logback retains
its existing 100 MB rollover, immediate gzip archives, 30-day/2 GB archive cap per
service. Docker stdout is a separate diagnostic copy, not another tail input.

An isolated Linux-volume fixture passed rename, late writes to the renamed open
file, new current file, truncation, append while Fluent Bit was stopped, restart,
compressed-file exclusion and no duplicate replay of five synthetic events.
It did not change production files. Rotation followed by immediate compression
while Fluent Bit is stopped remains a loss window: an unread compressed archive
is not collected. This limitation needs a deliberate collection/rotation design
review before claiming lossless collection during extended collector downtime.

## Storage lifecycle

Loki keeps filesystem TSDB v13 data on `loki_data`, 24h indices and 720h retention.
Compactor deletion delay is 2h, four deletion workers and 10m compaction interval.
WAL replay ceiling is 128 MB within the 512 MiB container; shutdown flush is on.
Ingestion limits are 4 MiB/s with 8 MiB burst, per-stream 1 MB/s with 2 MB burst,
1,000 global streams; query concurrency 4, timeout 30s, maximum interval 744h and
5,000 returned entries. Existing job/service/environment labels remain unchanged;
trace IDs are JSON fields, never labels. Retention is configured, not a hard quota;
physical expiry was not observed during this short test.

OpenSearch is intentionally single-node. The three legacy application indices
retain UUIDs, documents and mappings; only their replica counts change from one
to zero. New UTC event-date indices are `springboot-user-YYYY.MM.DD-logs`,
`springboot-learning-YYYY.MM.DD-logs`, `springboot-jwks-YYYY.MM.DD-logs`.
Existing `springboot-*-logs*` discovery remains compatible; queries naming an exact
legacy index must include the dated indices to find new records. No application
API changes. Numeric status/duration and searchable IDs keep the original mappings.

`opensearch/configure-log-retention.py --retention-days 30 --replicas 0` installs
three exact application-family templates and `springboot-dated-logs-retention`.
The policy automatically applies only to new `springboot-<service>-20*-logs`
indices and transitions to delete at index age 30d. ISM scheduling adds delay;
index age, rather than each document's timestamp, controls deletion. Existing
legacy indices are deliberately unmanaged and retained indefinitely. Their old
storage is not reclaimed by this policy. No historical index was deleted or
retroactively attached. Replicas=0 is guarded by actual single-node topology;
production multi-node deployments need an appropriate replica setting.

The original yellow state came from legacy application replicas. Application
indices are now green, but two ISM system-index replicas remain unassigned because
their primaries occupy the only node. Those system settings were preserved.

## Capacity and operations

| Component | Persistent data / retention | Memory / CPU |
| --- | --- | --- |
| Fluent Bit | tail DB + bounded output chunks on fluent_bit_state | 256 MiB / 0.5 |
| Loki | loki_data, 30 days | 512 MiB / 1 |
| OpenSearch | opensearch_data, new application indices 30 days; legacy indefinite | 2 GiB / 2, heap 512 MiB |
| Prometheus | prometheus_data, 15 days or 2 GB (whichever triggers first) | 512 MiB / 1 |
| Collector | otel_queue, 64 MiB payload admission capacity | 256 MiB / 0.5 |
| Tempo | tempo_data WAL + blocks, 72 hours | 512 MiB / 1 |
| Grafana | grafana_data, existing provisioning | 512 MiB / 1 |

All eleven application/observability main containers use json-file rotation,
10m x 3 compressed files: nominal 330 MiB combined before overhead/active-record
overshoot, excluding application file archives, backend storage and vendor file
logs. `OBS_DOCKER_LOG_MAX_SIZE` / `OBS_DOCKER_LOG_MAX_FILES` configure it. Database
and initializer logging was left unchanged. No daemon-wide settings changed.

Estimate daily backend growth from observed bytes/day; 30-day storage is roughly
30 times that rate plus indexing/WAL/compaction overhead, Tempo about three days
of sampled trace volume. Buffer outage coverage is capacity divided by incoming
serialized bytes/second per destination. No representative production workload
measurement or guaranteed outage duration is claimed. Baseline Docker filesystem
had about 892 GB free (7% used); this is a snapshot, not a capacity guarantee.
Maintain free space for WAL and compaction; retention does not prevent disk full.
No hard volume quotas, backups or HA were added in this development phase.

Run recovery tests sequentially, with a predeployment local snapshot preserved:

```powershell
python observability/verify-pipeline.py config
python observability/verify-pipeline.py health
python observability/verify-pipeline.py loki
python observability/verify-pipeline.py opensearch
python observability/verify-pipeline.py tempo
python observability/test-tail-recovery.py
python observability/verify-pipeline.py auth
python observability/verify-pipeline.py regression
```

Outage modes stop only the named project backend, restart its producer while down,
and restore the backend in finally. Use a maintenance window. `history` captures
predeployment samples; do not overwrite it after deployment. Local baseline and
evidence `.log` files are ignored. Synthetic fixture containers are stopped but
their dedicated volumes are retained; no cleanup/prune command is run.

If delivery stalls, check destination readiness, internal Fluent Bit 2020 storage
and retry counters, free disk, tail DB permissions, and Collector health/logs.
Restore the exact destination using `docker start springboot_project-<service>-1`
to avoid rerunning dependencies. Do not erase state to clear a queue.

No new public ingestion ports were added. Existing Loki/OpenSearch/Prometheus
host bindings remain loopback; Collector and Tempo remain Docker-internal only.
OpenSearch security-disabled local mode and internal plaintext were pre-existing;
they are not suitable for an untrusted shared production network. Production
transport/authentication, backups/restore, disk-full/crash exercises and capacity
acceptance remain Phase 6; dashboards/alerts remain Phase 5.

Supported option references: [Fluent Bit 3.2 storage](https://docs.fluentbit.io/manual/3.2/administration/buffering-and-storage),
[tail input](https://docs.fluentbit.io/manual/3.2/pipeline/inputs/tail),
[OpenSearch ISM](https://docs.opensearch.org/latest/im-plugin/ism/policies/),
[Loki retention](https://grafana.com/docs/loki/latest/operations/storage/retention/).
