# Observability incident response

Use existing authenticated Grafana and private Docker administration. External
paging is muted/unverified: until approved delivery exists, an explicitly assigned
operator must watch Grafana and local health checks. No responder roster or
production response-time commitment has been established by this assessment.

## Triage sequence

1. Record UTC, service/environment, impact, first symptom and recent deployment.
   Keep credentials, user IDs, JWTs, request bodies and private keys out of tickets.
2. Open Microservices Overview and Observability Infrastructure. Compare `up`,
   target errors and API readiness. Identify an application failure versus a
   telemetry pipeline failure; dashboards alone can fail when their datasource is
   down. Preserve a bounded time window of sanitized evidence.
3. For HTTP errors/latency, inspect route templates/statuses and traffic volume.
   Check JVM GC/heap/CPU/executors and Hikari pending/utilization. Never infer an
   attack from one401 or a security counter without context.
4. Find a known safe correlation ID in Loki. Match service, timestamp, route,
   numeric status and duration; follow TraceID into Tempo when sampled. Confirm
   Learning server→client→User server if cross-service. Compare OpenSearch source
   events when delivery differs. IDs are diagnostics, not authenticated identity.
5. For missing telemetry, check the appropriate row below. Restore the affected
   destination/connectivity before restarting collectors or increasing queues.
   Never discard queue state, tail DBs or volumes to obtain a green dashboard.
6. Verify recovery using a new bounded authorized request, target health, both log
   destinations, actual trace storage and queue drain. Keep the incident open if
   only the process is healthy but data delivery has not resumed.

| Signal | First investigation | Safe response / limitation |
| --- | --- | --- |
| ServiceDown / MissingMetrics | API readiness, scrape lastError,9091 exposure and target discovery | Preserve auth; do not publish Actuator to bypass a scrape failure |
| High5xx / error ratio | Traffic guard, statuses, bounded routes, safe errors, release changes | Expected4xx may dominate; do not change thresholds just to clear alerts |
| High p95/p99 | Histogram traffic, slow routes, pool waits, GC and sampled traces | Low-traffic NaN is not zero latency or an outage |
| Hikari saturation/pending | Pool maximum, wait/acquire latency, DB connectivity and transaction duration | Do not increase pools without database capacity review |
| Collector queue/export failure | Tempo ready/query, exporter logs, queue size/capacity and volume free space | Retry recovery may succeed; no exactly-once or crash proof |
| Fluent Bit delivery failure | Output name, readiness, retries/drops, FS chunks and current source path | Compression while stopped can strand unread history; preserve evidence |
| Loki push/flush failure | Push status, WAL, compactor, storage free space/permissions | Do not delete chunks/WAL; verify query plus fresh delivery |
| Tempo failure | Internal ready/query, WAL/block paths, Collector queue | Stored log trace IDs may be unsampled or expired |
| OpenSearch yellow | Application primaries, system replicas and allocation reason | Known single-node system replicas are not fixed by deleting indices |
| Grafana evaluation Error/NoData | Datasource readiness, Prometheus queries, alert annotation and scheduling | No-data is not an automatic business recovery; external delivery is muted |
| Disk pressure | Actual mounted filesystem free bytes/inodes and growth contributors | No host-wide filling, pruning or emergency data deletion under this runbook |

## Communication and maintenance

Assign incident owner and next update time; record hypotheses as hypotheses.
If planned maintenance is approved, use a narrowly scoped expiring silence with
owner/reason/end time. Preserve the all-day delivery-disabled mute until a
separate notification-enablement approval. Existing groups wait1m, update5m and
repeat4h; the original global policy tree is unchanged. See [alerting.md](alerting.md)
for each threshold/runbook and the exact rule-local route.

Escalate a potential credential leak by preserving restricted evidence and
following the organization's credential incident process; do not print suspected
secrets into logs, shell history or tickets. This runbook does not authorize key
rotation, user/account modification or unrelated-session revocation.

Post-incident, document the affected interval, measured loss/duplicates if known,
which queries proved recovery and remaining uncertainty. Distinguish source bytes
never read, buffer rejection/drop, retry failures, backend expiry and query-range
mistakes. Add a reproducible isolated regression before changing collection
semantics. Crash/overflow, physical expiry and restore rehearsals belong to the
separately approved [Phase6B plan](phase6b-validation-plan.md).
