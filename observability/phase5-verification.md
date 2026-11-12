# Phase 5 verification — 2026-11-12

## A. Executive summary

Implemented and deployed eight version-controlled dashboards, five Prometheus
recording rules and 21 Grafana Unified Alerting rules to **springboot_project**.
Actual installed versions: **Grafana 12.2.0**, **Prometheus 3.13.5**. All nine
dashboards (eight new plus the original), 21 alerts and five recording rules are
loaded. All nine scrape targets are UP. All 89 panel expressions were queried
against the actual datasources. All alert queries evaluate healthy; final states
are inactive/Normal. External notification delivery is **NOT VERIFIED and muted**;
this is not a claim of production-ready paging.

Only Grafana and Prometheus were recreated. Collector was restarted once to enable
its validated internal metrics reader. All applications retained container identity
and start time. All 16 `jp_dev` containers and all 93 pre-existing volumes were
preserved. No commit, push, branch change, key regeneration or unrelated repository
modification occurred. Phase 6 was not implemented.

## B. Baseline findings

Inspected base/debug Compose, environment examples and effective environment
configuration in memory, Grafana provider/datasources/original dashboard,
Prometheus, Loki, Tempo, Collector, Fluent Bit and OpenSearch configurations,
Phase 4 verification, logging pipeline, tracing, metrics, structured logging and
other observability documentation. No credentials were printed or written into
tracked artifacts. All submodule worktrees were clean at inspection, but their
HEADs already differed from the root gitlinks; that state was preserved.

Docker initially had no Linux-engine pipe. The user started Docker Desktop; the
read-only safety snapshot was then captured before deployment. An initial Loki
readiness check saw startup HTTP 503; it subsequently became ready. The immutable,
ignored `phase5-baseline.log` records all 34 containers (18 project, 16 unrelated
`jp_dev`), 93 volume names, persistent mounts, one existing dashboard and its body,
three datasources, zero alert rules, existing contacts/policy, targets, versions
and backend readiness. It refuses accidental overwrite.

Datasource UIDs: `loki`, `prometheus`, `tempo`. Existing policy receiver:
`grafana-default-email`; existing contact API identifies a default email receiver.
No real destination or transport was configured by this work. Existing Loki
derived fields and Tempo trace-to-log configuration already supported navigation.
No Prometheus recording/alert rules existed. Collector internal metrics were
disabled; Fluent Bit and the other native infrastructure metrics endpoints were
available but not scraped.

## C. Dashboard inventory

All dashboards use folder **Observability**, stable folder UID `observability`,
stable `sb5-*` dashboard UIDs, schemaVersion 41, one-hour range, 30-second refresh,
environment/service filters, consistent units/descriptions and explicit gaps for
missing data. File provisioning preserves the original provider, disables deletion
and uses no credentials. New UID collisions were checked against the baseline.

| Dashboard | UID | Content | Datasources |
| --- | --- | --- | --- |
| Microservices Overview | `sb5-overview` | Availability; request/4xx/5xx rates; error percentage; p50/p95/p99; volume; errors; JVM memory, CPU, uptime | Prometheus, Loki |
| HTTP Performance | `sb5-http` | Service/route/method/status throughput; 4xx/5xx/errors; percentiles; slow endpoints; histogram heatmap; managed HTTP client rate/latency | Prometheus |
| JVM & Runtime | `sb5-jvm` | Heap used/max/ratio, nonheap, GC frequency/time/mean, threads, process/system CPU, uptime, executor activity/capacity/queue, files/buffers | Prometheus |
| Database & Connection Pools | `sb5-database` | Hikari active/idle/pending/max, utilization, acquisition mean/max, timeouts; User/Learning only | Prometheus |
| Security & Authentication | `sb5-security` | Actual operation/result counter categories, authentication failures, authorization denials, event breakdowns, 401/403, safe rejection logs | Prometheus, Loki |
| Centralized Logging | `sb5-logging` | Service/severity volume, WARN/ERROR, recent errors/warnings, HTTP failures, correlation/trace-filtered records | Loki |
| Distributed Tracing | `sb5-tracing` | Service p95/p99/rate, Tempo Explore search/slow/error links, safe errors, investigation workflow | Prometheus, Loki, Tempo links |
| Observability Infrastructure | `sb5-infrastructure` | Target health, scrape time, Collector queue/export/refusal, Fluent Bit delivery, Loki/Tempo ingestion/storage failures, Grafana alert counts, Prometheus memory | Prometheus |

[Dashboard inventory](dashboard-inventory.md) enumerates every panel, variable and
datasource; [dashboards.md](dashboards.md) covers operator use and implementation.
Logging adds correlation and trace regex filters; database excludes JWKS;
infrastructure adds the six real component service values. The original
`springboot-application-logs` definition is unchanged.

## D. Prometheus queries and rules

Five service/environment recording rules evaluate every 30 seconds with 5-minute
windows: `sb:http_requests:rate5m`, `sb:http_5xx:rate5m`,
`sb:http_errors:ratio5m`, `sb:http_p95:seconds5m`, `sb:http_p99:seconds5m`.
Definitions are in `prometheus/rules/phase5.json`; details in dashboards.md.
Actuator traffic is excluded. Reachable targets without business observations
receive zero request rate; absent telemetry never receives an unconditional zero.
Error ratios are absent at zero traffic. Route dashboards query bounded raw `uri`
series, retaining route information without duplicating high-cardinality rules.

Rates precede aggregation; `histogram_quantile` preserves `le` and service/env,
optionally `uri`. No averaging of percentiles, raw request paths or invented
metrics. Fixed Phase 2 buckets are unchanged. Low-volume percentile NaN remains
undefined rather than fake zero. Hikari/heap ratios reject nonpositive maxima.

Installed promtool accepted config and five recording rules. Five isolated native
test scenarios / eleven expression assertions verify missing error series, zero
traffic, reachable-but-never-used services, absent telemetry, known 10% errors and
known histogram p95 interpolation. All five runtime recording rules report
`health=ok`. All 21 alert PromQL expressions were queried successfully.

## E. Logging and tracing

Loki's job/service/environment labels are unchanged. JSON parsing happens at query
time; optional fields use permissive default regex filters and parsing errors are
excluded. A live query caught an incorrectly escaped dotted JSON field during
implementation; it was corrected to a LogQL backtick expression and revalidated.
No trace, span, correlation or user identifier was promoted to stream labels.

Three actual Tempo TraceQL search forms passed: service/environment, slow requests
and error traces. Actual authenticated trace:
`ad583d826ce342e7b0210294e1c699fa`. Verified parent sequence:
remote → Learning server `eb40b85c61c95021` → Learning HTTP client
`911f7c2477ad0998` → User server `e4a5564fca43b20a`.
Both log stores had exactly two core matching completions with correct IDs/status.
The real Loki derived-field regex extracted this ID and Tempo's proxy resolved it;
the reverse trace-ID log query returned the corresponding records.

No service graph, span-derived metrics, TraceQL metrics generator or second metrics
pipeline was added. Root sampling remains **10%**. Controlled sampled parents were
used for verification. Browser filter/link interpolation, heatmap rendering,
waterfall UI and navigation clicks remain **NOT VERIFIED** manually.

## F. Infrastructure monitoring

Six native internal endpoints now join the three application targets in the same
Prometheus: Prometheus9090, Loki3100, Tempo3200, Collector8888, Fluent Bit2020 at
`/api/v1/metrics/prometheus`, Grafana3000. No new host ports or exporter containers.
Collector Contrib0.143.0 native validation accepted a `normal`-level pull reader
with explicit no-unit/no-type-suffix translation. Actual observed names include:

| Component | Real monitored metrics |
| --- | --- |
| All collected services | `up`, `scrape_duration_seconds` |
| Collector | `otelcol_exporter_queue_size`, `otelcol_exporter_queue_capacity`, `otelcol_exporter_send_failed_spans`, `otelcol_receiver_refused_spans` |
| Fluent Bit | `fluentbit_output_errors_total`, `fluentbit_output_retries_failed_total`, `fluentbit_output_dropped_records_total` |
| Loki | `loki_distributor_lines_received_total`, `loki_ingester_chunks_flush_failures_total`, `loki_ingester_wal_bytes_in_use`, push-route `loki_request_duration_seconds_count` |
| Tempo | `tempo_distributor_spans_received_total`, `tempo_ingester_failed_flushes_total` |
| Grafana | `grafana_alerting_alerts` and target health |
| Prometheus | `process_resident_memory_bytes` and target health |

Queue capacity observed **67,108,864**, matching the configured byte-sized persistent
queue; the upstream HELP text says batches generically, so only dimensionless
utilization is graphed. Endpoint UP does not establish end-to-end delivery; fresh
log/trace probes established that separately.

**Unavailable:** OpenSearch Prometheus cluster health, reliable backend/host free
capacity, Fluent Bit per-output buffer-capacity ratio, independently instrumented
cryptographic token failures. OpenSearch existing health API is checked by runtime
regression; its documented system replicas still make the cluster yellow while
application primaries remain active. Application `disk_*` meters do not represent
all backend volumes. No fabricated metric/alert or large exporter was added.

## G. Alert rules

[alert-rules.md](alert-rules.md) contains every exact expression, threshold,
pending period, stable UID, no-data mode, severity and runbook.
[alerting.md](alerting.md) provides the compact inventory and operational rationale.
The 21 rules cover ServiceDown, three MissingMetrics targets, High5xxErrorRate,
HighHTTPErrorRatio, HighP95Latency, HighP99Latency, HighHeapUsage, HighCPUUsage,
ExcessiveGCPause, HikariPoolSaturation, HikariPendingConnections,
CollectorExportFailures, CollectorQueueSaturation, FluentBitDeliveryFailures,
LokiIngestionFailures, TempoUnavailable, PrometheusTargetDown,
ElevatedAuthenticationFailures and ElevatedAuthorizationDenials.

Evaluation interval1m; pending2–15m; keep-firing1m. Error state is `Error` for all;
availability no-data is `NoData`, other no-data is `OK` with explicit missing-target
rules. HTTP alerts require 100 requests/5m, p99 requires1000. Severity is warning
or critical. Labels are bounded service/environment/severity plus phase, optionally
pool. Thresholds are development starting points, not approved production SLOs.

Final **21/21 health=ok, state=inactive**. Exact loaded expressions/pending/no-data/
error behavior match version-controlled files. Safe preview API tests returned
breach1, normal0, no-data empty, and exposed an intentional synthetic parse error.
No persisted synthetic alerts or service interruptions. Real elapsed pending/firing/
recovery state transitions under breach remain **NOT VERIFIED**.

**NOT IMPLEMENTED:** HighDiskUsage, StorageCapacityRisk, OpenSearch cluster-health,
Fluent Bit per-output buffer-saturation and distinct token-validation alerts,
because reliable supporting collected metrics are unavailable.

## H. Notifications

Existing contacts and the entire policy tree match the baseline. Rule-local routes
group by service/environment/severity, wait1m, group interval5m, repeat4h. All rules
reference the provisioned, API-verified all-day `phase5-delivery-disabled` mute.
Evaluation remains visible internally. No external notification test was sent.

`PHASE5_ALERT_RECEIVER` selects an existing receiver name; a separate inactive
webhook provisioning/Compose example uses an environment URL and allows recovery
messages. No recipient, URL or secret was invented. Instructions for explicit
authorization, enabling transport/routing, expiring silences and maintenance are
in alerting.md. External delivery/recovery delivery: **NOT VERIFIED**.

## I. Security and privacy

All original loopback bindings, unpublished metrics/ingestion endpoints, private
Actuator authorization and Grafana authentication are preserved. Collector8888
and Fluent Bit2020 remain internal. All twelve protected environment/key/test
credential fingerprints match earlier Phase 4 evidence. No real secret appears in
dashboard/alert definitions; static checks reject private-key/JWT/URL-credential
patterns and sensitive query dimensions. Authenticated telemetry checks found no
actual tested credentials, tokens or identity values in inspected logs/spans.
This is observed-window evidence, not a proof against all possible future inputs.

## J. Automated tests — exact results

Executed from root with existing debug configuration:

| Command / check | Result |
| --- | --- |
| `python observability/build-phase5.py` | exit0; 8 dashboards, 5 recording rules, targets, alerts/reference docs generated |
| `python observability/verify-phase5.py static` | exit0; 306 PASS checks |
| `python observability/verify-phase5.py preflight` | exit0; versions, collisions, contact receiver, mounts, sampling, internal ports and environment passed |
| `python observability/verify-phase5.py native` | exit0; Compose, installed promtool config/rules, 5 synthetic scenarios/11 assertions passed |
| Collector0.143.0 `validate --config=/etc/otelcol/config.yml` via one-off `compose run --rm --no-deps` | exit0 |
| Active container `promtool check config /etc/prometheus/prometheus.yml` | exit0; 1 rule file / 5 rules SUCCESS |
| `python observability/test-phase5-alerts.py` | exit0; breach, normal, no-data, execution-error previews passed |
| `python observability/verify-phase5.py runtime` | exit0; 270 PASS checks, 89 panel queries |
| `python observability/verify-metrics.py --credentials observability/local-test-credentials.json` | exit0; actual meter/histogram/client/security/pool/private-listener/log/JWT checks passed |
| `python observability/verify-baseline.py --runtime` | exit0; base/debug settings, health, correlation, log metadata, storage and Grafana passed |
| `python observability/phase5-regression.py` | exit0; authenticated trace chain/privacy, refresh/logout, JWKS, buffering/retention/log rotation, real search/navigation and protected fingerprints passed |
| `git diff --check` | exit0 |

Earlier validation attempts found and corrected: read-only /tmp in the isolated
promtool test container (tests now use bounded temporary tmpfs), unsupported Tempo
datasource health API404 (now uses readiness/query), startup-readiness timing and
Loki JSON quoting. Baseline/metrics/tracing/pipeline verifiers now recognize the
reviewed Phase 5 mounts and select the three application targets from the expanded
nine-target inventory; no health requirement was weakened.

No Java/application configuration changed, so Maven suites were not rerun in
Phase 5. Phase 4's 300 passing Maven tests are historical evidence, not claimed
as a new test run. Local ignored result logs hold exact static/native/runtime/
preview evidence; `phase5-regression-evidence.log` contains sanitized real trace
and pipeline evidence. No secret-bearing baseline is tracked.

## K. Runtime deployment verification

Initial deploy02:03UTC recreated Grafana/Prometheus with `up -d --no-deps --no-build
--pull never`, explicitly using `-p springboot_project` and both base/debug files.
Grafana retained its original persistent volume despite a pre-existing Compose
ownership-label warning. Database readiness, datasource identities, original
dashboard and contacts/policy verified preservation; no data removal occurred.
Collector restarted only after native validation. A later SIGHUP loaded improved
idle recording rules without recreating Prometheus. Grafana restarts loaded alert
updates and verified idempotence. Only those three services were affected.

Readiness: Grafana database OK, Prometheus ready, Loki ready, Tempo ready. All three
APIs healthy; all three application and six infrastructure scrape targets UP.
Nine provisioned dashboards and 21 alerts exist without duplicates after restart.
All panel datasource UIDs resolve, loaded expressions match source, and real
PromQL/LogQL requests succeed. All five recording rules and21 alert rules are
healthy. Contact points/policy unchanged, mute interval loaded. Actual trace/log
delivery and search/navigation query paths passed.

Final quiet-traffic snapshot had seven legitimately empty query results: mean
connection acquisition, two zero-traffic error-ratio panels, ERROR trend and three
recent-error log panels. Metrics/latency counters were verified using real traffic
in the metrics regression earlier; no error data was fabricated. Empty error logs
and undefined idle ratios do not establish missing telemetry. No browser rendering
claim is made. Grafana's pre-existing optional plugin background installer reports
read-only /tmp failures; native built-in panels and Tempo Explore API work. No
unrequested plugin or writable-root change was introduced to hide that limitation.

## L. Phase 0–4 regressions

PASS: structured JSON, metadata, correlation propagation, Micrometer/histograms,
protected Prometheus listeners, existing JWT login/refresh rotation/logout,
Learning→User internal JWT, JWKS public bodies and actual distributed span parenting.
PASS: fresh Loki/OpenSearch logs and Tempo traces, once-only completions, safe
diagnostics, persistent Collector queue config/mount, Fluent Bit FS chunks/tail DB
configuration, Loki720h/Tempo72h retention, OpenSearch new dated-index ingestion,
Docker10m/3 rotation and original datasources. Current Fluent Bit process reported
zero permanently exhausted retries/dropped records; recovered startup retries were
visible. No account was created/modified; test sessions were logged out.

Pipeline outage/crash/overflow tests and actual physical retention deletion were
not repeated or claimed. Phase 4 known compressed-rollover loss window and
unmanaged legacy OpenSearch indices remain. Baseline historical Prometheus samples
were not newly timestamp-snapshotted in Phase 5; persistent volume identity and
existing TSDB/query availability were verified without a new exact-sample claim.

## M. JWKS cross-project compatibility

No API, key, issuer, network, kid, response or application-container change. Both
public JWKS responses match previous fingerprints/bodies. Internal JWT and actual
Learning→User communication passed. `japanese-learning` requires **no changes**;
no separate implementation prompt is needed because there is no contract impact.
All16 `jp_dev` containers retain identity/start time; that repository was untouched.

## N. Acceptance matrix

| Requirement | Status | Evidence / limit |
| --- | --- | --- |
| 1 Baseline inspection / actual versions | PASS | Config/docs/git plus live API/metric snapshot |
| 2 Deployment safety / persistent data | PASS | 34 containers/93 volumes baseline; only3 affected services |
| 3 Version-controlled stable provisioning | PASS | Native Grafana load, no UID collisions/duplicates, original preserved |
| 4 Overview | PASS | Metrics/log panels and actual query validation |
| 5 HTTP | PASS | Bounded routes, correct buckets, client metric from real authenticated traffic |
| 6 JVM/runtime | PASS | Actual memory/GC/thread/CPU/executor/process metrics |
| 7 Database/pools | PASS | Actual Hikari meters; no JWKS panels |
| 8 Security | PASS | Actual bounded operation/result categories, safe logs, limitations stated |
| 9 Logging | PASS | Live LogQL/filter expressions; existing trace derived field preserved |
| 10 Tracing query/search/navigation paths | PASS | Real Tempo searches/trace and correlated Loki query |
| 10 Browser clicks/rendering | NOT VERIFIED | Manual UI acceptance remains |
| 11 Infrastructure metrics | PASS | Six real native targets; unavailable coverage explicitly excluded |
| 12 Recording rules | PASS | Native syntax + five scenarios/11 assertions + healthy runtime |
| 13–14 Unified alert provisioning / supported alerts | PASS | 21 exact loaded definitions, healthy evaluations, preview tests |
| 14 Unsupported capacity/OpenSearch/buffer/token alerts | NOT VERIFIED | NOT IMPLEMENTED: reliable supporting metrics absent |
| 15–16 Internal evaluation / safe routing | PASS | Rule-local routing, all-day mute, original policies preserved |
| 15 External delivery / recovery notifications | NOT VERIFIED | No authorized destination test; delivery muted |
| 16 Live elapsed pending/firing/recovery transition | NOT VERIFIED | No intentional service disruption; preview only |
| 17 Security/privacy | PASS | Endpoint protections, hashes, safe artifacts/auth telemetry checks |
| 18 Automated validation | PASS | Native tools plus actual Grafana/Prometheus/Loki/Tempo APIs |
| 19 Runtime deploy / health / persistence / unrelated containers | PASS | Exact only-affected comparison; original volumes all retained |
| 20 Phase0–4 regression | PASS | Authenticated/JWKS/log/metric/trace/config checks; historical limits retained |
| 21 Cross-project compatibility | PASS | No contracts changed; jp_dev untouched |
| 22 Documentation / environment operations | PASS | Inventory, queries, rules, routing, runbooks, evidence and examples |
| 23 Git constraints | PASS | No commits/push/branch reset; original submodule state preserved |
| 24 Final verification and limitations | PASS | This A–P report, inventories and operator docs |
| Production paging acceptance | NOT VERIFIED | External delivery and operator/UI gates outstanding |

## O. Git and container inventory

Root changes: `.env.example`, `.gitignore`, `docker-compose.yml`, observability
README/Grafana README, Collector telemetry and Prometheus configuration; approved
mount/target changes in four existing verification scripts. New files: eight
dashboard JSONs, Grafana alert provisioning JSON, target/rule/test JSONs, deterministic
builder, runtime/discovery/regression/static/native/preview verification helpers,
inactive webhook/Compose examples, machine inventory and dashboard/alert/verification
documentation. `git diff --check` passes. Ignored logs/credentials/caches are not
tracked. No application source files changed.

| Submodule | Preserved checked-out HEAD | Worktree |
| --- | --- | --- |
| User | `e7991b34d310b94696469dda30c108645e06d00e` | clean |
| Learning | `f6a61f6a0d1284adc831fa6f04b83ce23c02faa2` | clean |
| JWKS | `7879d155eddb45fb079800709f49a3c3a1566120` | clean |

Root reports all three submodule pointers modified exactly as at task start; they
were not staged or altered. Root tracked work remains uncommitted.

Recreated: `springboot_project-grafana-1`, `springboot_project-prometheus-1`.
Restarted in place: `springboot_project-otel-collector-1`. Grafana was restarted
again for updated alert provisioning/idempotence; Prometheus received SIGHUP for
recording rules. All other31 baseline containers, including applications,
databases, initializers and16 `jp_dev`, retained ID and start time. All original
volume mount names remain. Temporary native validation containers were one-off
`--rm` fixtures; no persistent cleanup/delete/prune command was used.

## P. Outstanding limitations / stop boundary

External notification authorization/transport/recovery delivery, manual browser
acceptance and real elapsed alert transitions remain unverified. Production SLOs,
responder ownership, realistic load/capacity and disk metrics need review. Host
storage/OpenSearch exporters require separate justification; they were not added.
Phase 6 HA, TLS/auth/network hardening, capacity sizing, backup/restore and
disk-full/crash/retention acceptance remain follow-up items. Earlier Phase 4
limitations remain explicit. Work stops at Phase 5 for review; no commit or push.
