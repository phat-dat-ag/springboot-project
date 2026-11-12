# Grafana dashboards — Phase 5

Open Grafana at **http://localhost:3077**, sign in with the existing account and
choose **Dashboards → Observability**. Start at
[Microservices Overview](http://localhost:3077/d/sb5-overview). The header dropdown
links all eight Phase 5 dashboards and carries the selected variables/time range.
Ports are local deployment values; check Compose when deploying elsewhere.

## Inventory and purpose

Every panel and variable is listed in [dashboard-inventory.md](dashboard-inventory.md)
and [the machine-readable inventory](grafana/phase5-inventory.json).

| Dashboard / stable UID | Purpose | Datasources |
| --- | --- | --- |
| Microservices Overview / `sb5-overview` | Scrape availability, throughput, 4xx/5xx/error fraction, p50/p95/p99, volume, errors, JVM memory, CPU and uptime | Prometheus, Loki |
| HTTP Performance / `sb5-http` | Service/route/method/status traffic, errors, percentiles, slow endpoints, duration heatmap and internal client performance | Prometheus |
| JVM & Runtime / `sb5-jvm` | Heap/max/utilization, non-heap, GC rate/pause/mean, threads, CPU, uptime, executor active/max/size/queue, descriptors and buffers | Prometheus |
| Database & Connection Pools / `sb5-database` | Hikari active/idle/pending/max/utilization, acquisition mean/window maximum and timeouts | Prometheus |
| Security & Authentication / `sb5-security` | Bounded authentication/authorization events, operation/result trends, 401/403 and safe logs | Prometheus, Loki |
| Centralized Logging / `sb5-logging` | Volume by service/severity, WARN/ERROR, failures, recent/correlated records and trace navigation | Loki |
| Distributed Tracing / `sb5-tracing` | Service latency and actual Tempo Explore searches for selected services, slow and error traces | Prometheus, Loki; Tempo links |
| Observability Infrastructure / `sb5-infrastructure` | Scrape health, Collector queue/export/refusal, Fluent Bit output delivery, Loki/Tempo ingestion/storage failures, Grafana alert counts, Prometheus memory | Prometheus |

The existing `springboot-application-logs` dashboard remains intact. The database
dashboard restricts its service variable and queries to User/Learning; JWKS has no
database. Infrastructure adds six bounded component service choices to the three
application services. All eight dashboards have environment/service selectors,
one-hour defaults, browser timezone and a 30-second refresh. Logging also exposes
correlation/trace regex text filters; `.*` includes records missing optional fields.
These filters affect detailed log panels; volume panels deliberately retain context.

## Datasource and provisioning architecture

Existing datasource UIDs and URLs are unchanged: `prometheus` →
`http://prometheus:9090`, `loki` → `http://loki:3100`, `tempo` →
`http://tempo:3200`. Loki remains default. Dashboards contain no credentials.

The existing YAML file provider owns `/etc/grafana/dashboards`, folder UID
`observability`, scans every 30 seconds, disables deletion and prohibits UI saves
of provisioned definitions. JSON uses Grafana's classic schemaVersion 41, accepted
by the actual installed Grafana **12.2.0**. No legacy graph/singlestat panels or
`__inputs` import substitutions are used. Native supported panel types are
timeseries, logs, heatmap and text. Unrelated dashboards are protected by checking
UID collisions against the predeployment snapshot; new UIDs use the `sb5-` prefix.
Copy a dashboard to a different UID for personal customization.

`build-phase5.py` generates the eight JSON files, recording rules, target discovery
files, alert definitions and inventories. Edit that source for generated changes
and regenerate. The original application-log dashboard is not generated or edited.

```powershell
python observability/build-phase5.py --environment development
python observability/verify-phase5.py static
python observability/verify-phase5.py native
```

Target labels must match the application's `DEPLOYMENT_ENVIRONMENT`. For another
environment, explicitly pass the matching `--environment` value and review the
generated target/rule files. Dashboard variables discover the environments from
actual `app_build_info`; they do not silently relabel production as development.
File discovery refreshes in 30 seconds. Prometheus uses `honor_labels: true` only
for its trusted application endpoints, preserving their service/environment labels
and adding those same bounded labels to generated `up` metrics.

## PromQL conventions

Counters use `rate` before aggregation; volume uses `increase` over the selected
range. Interactive rates use `$__rate_interval`. Reused service summaries use a
5-minute window, evaluated every 30 seconds. Actuator routes are excluded from
HTTP business-traffic summaries so periodic scrapes do not mask idle services.
HTTP route labels remain framework `uri` templates, capped in Phase 2. Top route
panels show at most 10/15 series; no user IDs, raw paths or query strings are added.

Five recording rules are in `prometheus/rules/phase5.json`:

| Name | Meaning |
| --- | --- |
| `sb:http_requests:rate5m` | Requests/second by service/environment, excluding Actuator; zero fallback only for reachable targets |
| `sb:http_5xx:rate5m` | Server failures/second; absent error counters become zero only alongside known request telemetry |
| `sb:http_errors:ratio5m` | (4xx + 5xx)/requests, emitted only for positive traffic |
| `sb:http_p95:seconds5m` | Approximate p95 from cumulative duration buckets |
| `sb:http_p99:seconds5m` | Approximate p99 from cumulative duration buckets |

Percentiles use `histogram_quantile(q, sum by (service,environment,le)
(rate(http_server_requests_seconds_bucket[5m])))`, adding `uri` only for route
panels. They never average percentiles. The heatmap retains `le`; Prometheus
heatmap format converts cumulative buckets for visualization. Server/client fixed
buckets remain Phase 2's 5ms–10s/+Inf boundaries. Quiet histograms can produce NaN;
they are not converted to zero latency. Client meters appear only after a real
managed client call. No extra instrumentation was added to fill panels.

Zero observed traffic, missing series and scrape failure are different states.
There is no unconditional `or vector(0)`. Missing measurements remain gaps, with
"No telemetry" for undefined values. Ratios exclude unknown/nonpositive maxima;
CPU and ratios use fraction units, memory uses bytes, durations use seconds.

## Loki and Tempo investigation

Loki selectors keep `job`, `service`, `environment`. Severity and IDs are parsed
from JSON at query time. `| __error__=""` excludes malformed records safely.
Dotted fields use an explicit JSON extraction, for example:

```logql
{job="springboot",service="learning-api",environment="development"}
  | json category=`["error.category"]`
  | __error__=""
  | category=~"authentication|authorization"
```

Trace/correlation/span IDs never become stream labels. Expand a log entry and
select **TraceID → View trace**. Existing Loki derived fields extract the real
32-hex JSON trace ID into Tempo. Tempo's existing trace-to-logs configuration maps
resource `service.name` to the service label, filters by trace ID and adds a
one-minute time margin. The authenticated regression verifies both underlying
query paths and actual IDs, not browser clicks.

The tracing dashboard provides encoded Explore links with service/environment
variables. Searches use actual Tempo 2.9.0 TraceQL resource attributes and intrinsic
`duration`/`status`. No service graph, span metrics or TraceQL metrics pipeline was
enabled. Preserve 10% parent-based sampling: a log's trace ID may have no stored
trace. HTTP 4xx is not automatically an error span. Narrow the range and open the
server/client waterfall; then follow logs around the same time.

Manual acceptance: change filters and time range in a browser, open all three
Tempo links, inspect the heatmap, click log→trace and trace→logs. API verification
does not establish browser layout, link interpolation or click behavior.

## Troubleshooting and limits

Check target `lastError`, datasource health, readiness and Grafana provisioning
logs first. Widen a quiet service's time window and generate authorized traffic.
Empty ERROR panels are expected in a healthy deployment; do not fabricate failures
to fill them. Executor maximum may be a very large configured default rather than
practical capacity. GC pause mean is not a percentile. Hikari acquisition maximum
is a Micrometer time-window maximum. Security operation counters classify terminal
HTTP outcomes, not individual identity-provider or cryptographic failures.

OpenSearch has no Prometheus exporter in this deployment. Backend filesystem free
capacity, Fluent Bit per-output buffer saturation and independent token-validation
counts remain unavailable. Application `disk_*` gauges describe their own mounts
and are not reliable evidence of backend-volume headroom. No disk-capacity alert,
OpenSearch health gauge or buffer-percentage panel is fabricated. See
[alerting operations](alerting.md) and [Phase 5 evidence](phase5-verification.md).
