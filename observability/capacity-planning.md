# Observability capacity assessment

Observed 2026-11-12 during bounded development validation. These are snapshots,
not production sizing, throughput limits or sustained-pressure measurements.
[phase6-measurements.json](phase6-measurements.json) contains exact values and UTC.
No stress, disk-filling, outage or workload generator was run.

## Measured resource snapshot

| Component | Docker CPU sample | Memory used / limit |
| --- | ---: | --- |
| User API | 0.31% | 345.7MiB /1GiB |
| Learning API | 0.13% | 313.8MiB /1GiB |
| JWKS API | 0.12% | 206.9MiB /1GiB |
| MySQL | 0.44% | 453.4MiB /1GiB |
| PostgreSQL | 4.53% | 59.53MiB /1GiB |
| Grafana | 0.35% | 134.2MiB /512MiB |
| Prometheus | 0.83% | 83.74MiB /512MiB |
| Loki | 1.03% | 173.5MiB /512MiB |
| OpenSearch | 3.34% | 1.004GiB /2GiB |
| Fluent Bit | 0.05% | 17.55MiB /256MiB |
| Collector | 0.10% | 40.88MiB /256MiB |
| Tempo | 0.30% | 74.05MiB /512MiB |

Docker CPU percentages are point samples, not utilization of each configured CPU
limit. Memory/caches and JVM committed/used heap are different measurements. At
the recorded Prometheus sample, heap occupancy was approximately User21.7%,
Learning21.3%, JWKS15.8%; Hikari active/max0 with pending0; Collector queue
utilization0. OpenSearch heap60%. No sampled saturation was observed, but there is
no peak, soak or failure-headroom proof. Shared host pressure can affect both
Compose projects even with unchanged container identities.

174 actual dashboard query evaluations (all-service plus Learning/environment
filters) took2.43–40.45ms, median6.19ms client-observed locally. This is not Grafana
browser render latency or concurrent-user performance. Five-minute diagnostic
ingestion samples were about107.7 Loki bytes/s and0.186 Tempo spans/s. These rates
are not representative business traffic and cannot size production buffers.

OpenSearch's node filesystem reported955,883,905,024 available bytes of
1,081,101,176,832 total (about890GiB available). This is that node's storage view,
not a verified Windows host free-space budget or continuous per-volume pressure
alert. No reliable collected host/backend filesystem capacity alert exists.

## Budgets and storage growth risks

| Store | Configured policy | Important additional space |
| --- | --- | --- |
| Source logs |100MB rollover,30days/2GB archives per app | Active files, gzip timing and unread archive loss window |
| Fluent Bit |64M Loki +3×32M OpenSearch outputs;16 chunks up/16M backlog memory | Shared chunks, DB/WAL/metadata; logical budgets are not disk quotas |
| Collector |64MiB serialized trace admission,2 workers | DB/WAL, fsync/compaction scratch and volatile pre-admission batches |
| Loki |30days,4MiB/s ingest/8MiB burst;128MB WAL replay ceiling | Index/chunks, WAL, compactor and delayed deletion |
| OpenSearch |30days for new dated app indices,1 primary/0 replicas | Index overhead/merges, vendor logs;3 unmanaged legacy app indices grow without this lifecycle |
| Tempo |72hours,5-minute blocks | WAL, blocks, compaction and live traces |
| Prometheus |15days or2GiB, whichever triggers | WAL/head/compaction; size retention is not a filesystem quota |
| Docker diagnostics |10m×3 compressed files on11 services | Nominal330MiB budget plus active-record/metadata overhead; databases not covered by that shared policy |

Estimate destination backlog coverage as `usable buffered bytes / peak serialized
bytes per second` **per output**, then subtract safety margin for overhead and
concurrent bursts. Source unread coverage is separately bounded by uncompressed
file retention; it is not part of the collector buffer budget. Measure duplicates,
compression/index amplification, WAL and compaction peaks before using this model.

Approximate retained data is measured backend daily growth × retention age plus
index/WAL/compaction margin. Do not multiply raw-log size by30 and assume it equals
OpenSearch disk use. Collect at least daily filesystem/index/TSDB samples over a
representative workload and real retention cycles; maintain rate/size forecasts,
capacity ownership and alarms. Legacy OpenSearch indices need a separate approved
archive/retention decision; no historical cleanup was performed.

## Production sizing gates

Agree request mix/RPS/concurrency, route/cardinality budget, error mix, log verbosity,
sampling policy, notification volume, dashboard concurrency and outage tolerance.
Measure CPU/RSS/heap/GC/pool wait, p95/p99, accepted/refused/dropped telemetry,
queue depth/drain time, source-read lag, backend bytes/day and query latency under
bounded representative load. Define abort thresholds and reserve capacity for
backlog recovery. Assess MySQL/PostgreSQL and storage separately from API memory.
No safe production RPS ceiling or guaranteed outage duration is established.

Add justified host/storage/OpenSearch instrumentation in a separate reviewed
change; native APIs used for this assessment are not a Prometheus alert source.
Do not invent Fluent Bit buffer percentage from `fs_chunks` or treat process UP as
successful delivery. See [Phase6B performance/storage plans](phase6b-validation-plan.md)
for isolation, resource ceilings and approval requirements.
