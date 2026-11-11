# Phase 2 metrics contract and operations

This is the metrics contract for all three independent Spring Boot services.
Deployment/test evidence is in [phase2-verification.md](phase2-verification.md).
The [logging contract](structured-logging.md) and existing JWT/API contracts remain.

## Architecture and security boundary

Boot/Micrometer -> Prometheus registry -> private HTTP scrape -> Prometheus TSDB
-> Grafana Prometheus datasource. Logs still use files -> Fluent Bit -> Loki and
OpenSearch. OTLP metrics/log exports remain disabled. Phase 3 adds only trace
export through Collector/Tempo; see [tracing.md](tracing.md).

Each service adds the Boot-managed `io.micrometer:micrometer-registry-prometheus`.
Boot/Java/encoder versions are unchanged. User retains its existing disabled OTLP
registry; the Phase 3 tracing bridge is not a second metrics pipeline.

`MetricsEndpointConfiguration` adds an opt-in Tomcat connector at container port
9091. A dedicated security chain at order -100 permits only GET
`/actuator/prometheus` on that actual connector. Every other request on that
connector is denied. The same Prometheus path on the application connector is
always denied, including authenticated/admin requests. Existing health/readiness/
liveness paths on 8080 and existing application security chains are unchanged.
This uses an extra connector rather than relocating all Actuator endpoints with
`management.server.port`, which would move the existing readiness URL.

Compose publishes **no API port 9091**. Only health and Prometheus are exposed by
Actuator, never `env`, `beans`, `configprops`, `heapdump` or `threaddump`. Default
standalone exposure remains health; the extra listener defaults off. Both listener
enablement and health,prometheus exposure are explicit in Compose.

**Trust boundary:** the existing private `springboot_project_default` bridge and
its attached containers are trusted scrapers. There is no scraper password or
TLS inside this bridge. This is network isolation, not a hidden URL or a claim of
per-container identity. Docker administrators and processes able to access private
container IPs are privileged/trusted. Do not attach untrusted workloads, publish
9091, or route public traffic directly to it. Production multi-tenant deployments
need network policy/TLS/authentication review before expanding this boundary.
No existing network, endpoint, key, port or consumer DNS name is changed.

Prometheus itself publishes only `127.0.0.1:${PROMETHEUS_HOST_PORT:-9090}:9090`.
Its HTTP API/UI is trusted local administration, unauthenticated on loopback and
the private bridge. No remote-write receiver, lifecycle reload API or admin API is
enabled. Grafana retains its existing authentication and Loki default datasource.

## Configuration

| Setting | Default / use |
| --- | --- |
| `METRICS_LISTENER_ENABLED` | false standalone; explicitly true in Compose |
| `METRICS_LISTENER_PORT` | 9091; fixed to match scrape targets in Compose |
| `MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE` | health standalone; Compose explicitly health,prometheus |
| `MANAGEMENT_PROMETHEUS_METRICS_EXPORT_ENABLED` | true with registry; set false to disable scrape registry |
| `MANAGEMENT_METRICS_ENABLE_ALL` | Existing global instrumentation flag, true |
| `PROMETHEUS_HOST_PORT` | Root Compose optional loopback port, 9090 |
| `management.metrics.distribution.slo.http.server.requests` | Fixed durations listed below |
| `management.metrics.distribution.slo.http.client.requests` | Same fixed durations |

Changing a scrape port requires updating both the listener and scrape target;
do not change just one. No real `.env` secret/value is rewritten for this phase.
Service/standalone examples document the opt-in; `.gitignore` protects the exact
optional `observability/local-test-credentials.json` path supplied for testing.

## Names, labels and instrumentation

Common labels are only `service` and `environment`, using canonical Phase 0 names:
`user-learning`, `learning-api`, `jwks-service`. Version belongs on `app_build_info`
as `version`, avoiding release-label multiplication of every meter. Prometheus adds
`job="springboot"` and `instance="<compose-service>:9091"` during collection; it does
not add duplicate service/environment target labels.

| Exported name | Source | Main labels beyond service/environment/job/instance |
| --- | --- | --- |
| `app_build_info` | One constant gauge in MetricsConfiguration | version |
| `http_server_requests_seconds_count`, `_sum`, `_max`, `_bucket` | Boot servlet observations | method, uri, status, outcome, error/exception as supplied by framework; bucket adds le |
| `http_client_requests_seconds_count`, `_sum`, `_max`, `_bucket` | Boot-managed RestClient observations | method, uri, status, outcome, client_name, error/exception; bucket adds le |
| `jvm_memory_used_bytes`, `jvm_memory_committed_bytes`, `jvm_memory_max_bytes` | JVM binder | area, id (bounded JVM memory pool name, not a request/account ID) |
| `jvm_gc_pause_seconds_count`, `_sum`, `_max` | JVM GC notifications | action, cause, gc; appear after events |
| `jvm_gc_live_data_size_bytes`, `jvm_gc_memory_allocated_bytes_total` | JVM GC binder | Framework-defined bounded JVM labels |
| `jvm_threads_live_threads`, `jvm_threads_daemon_threads`, `jvm_threads_states_threads` | JVM thread binder | state where applicable |
| `process_cpu_usage`, `system_cpu_usage`, `system_cpu_count`, `system_load_average_1m` | JVM/OS binders | Platform availability varies |
| `process_uptime_seconds`, `process_start_time_seconds` | Uptime binder | None |
| `executor_*` | Boot-supported managed executor binder | name, state where applicable; only instrumented executors |
| `hikaricp_connections_active`, `_idle`, `_pending`, `_max`, `_min` | Hikari native Micrometer integration | pool |
| `hikaricp_connections_acquire_seconds_count`, `_sum`, `_max` | Hikari acquisition timer | pool |
| `jdbc_connections_active`, `_idle`, `_max`, `_min` | Boot datasource pool binder | name |
| `app_security_events_total` | Terminal request classification | operation, result |
| `up`, `scrape_duration_seconds`, `scrape_samples_scraped` | Prometheus scrape engine | job, instance; these are target metrics, not application meters |

Exact live label sets and availability are recorded in the verification report.
User/Learning use their existing MySQL/PostgreSQL Hikari pools. JWKS has no JDBC
dependency/datasource and intentionally exports no Hikari/JDBC meters. No database
or new pool is introduced to manufacture metrics; pool sizing/behavior is unchanged.

HTTP timers are framework-owned. The logging filter does **not** record another
HTTP duration/count timer. Spring's default conventions supply route templates
(`uri`), bounded unmatched/unknown labels, and omit query strings. Never add user,
account, session, JWT/hash, correlation, trace/span, raw path or full-URL labels.
MeterFilters cap distinct URI tag values at 100 per server/client meter family;
excess series are denied, not renamed into an unbounded fallback. Review this
budget if adding many legitimate static endpoints. No URI IDs are intentionally
mapped to metric labels.

## Histograms and percentile limits

Fixed SLO boundaries in seconds:
`0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10`, plus `+Inf`.
Properties use integer duration syntax, including `2500ms`, supported by Boot's
duration binder. SLO buckets enable aggregatable Prometheus histograms without
the larger generated percentile bucket set or non-aggregatable client summaries.
No separately published `quantile` series is promised.

Each observed HTTP tag combination adds 12 bucket series plus count/sum/max.
Do not enable generated histograms or finer buckets globally without a cardinality/
memory review. Quantiles interpolate within these buckets and are approximate;
the highest finite bucket is 10 seconds. Adjust boundaries based on measured SLOs,
not arbitrary precision. Idle routes can yield NaN rate-based percentiles because
no requests occurred; this is not a scrape failure. Use a wider window or traffic.

## Security counters and exact ownership

`SecurityMetrics.completed` is invoked inside Phase 1's existing once-only final
completion guard, after final status is known. The observer does not change
authentication, authorization or response behavior. Classification is exclusive:

1. POST matched `/auth/login`: operation `login`, result success for 2xx else failure.
2. POST matched `/auth/refresh`: operation `refresh`, same result rule.
3. Other 401: `internal_authentication` for `/internal/` prefix, otherwise
   `authentication`; result failure.
4. Other 403: `authorization`, result failure.
5. Other requests do not increment this counter.

Seven possible operation/result pairs are pre-registered per service. There are
no user/token/exception-message labels. These represent **terminal HTTP results**,
not individual provider attempts: invalid login payloads and server failures on
those routes count as failed HTTP operations. A successful refresh can still fail
later delivery; this counter does not claim cryptographic issuance internals.
Management-port/published-port denial also counts as authorization rejection.
Do not sum this counter and HTTP request counters as if they were different events.
No independent Security-event listener counts the same request again.

## Internal HTTP client

Learning's existing `ServiceClientConfig` clones a Boot-managed `RestClient.Builder`,
which already carries the ObservationRegistry. `UserServiceClient` uses
`/internal/users/{id}` as a URI template. No manual timer or second interceptor is
added. Built-in HTTP observations record status and duration once, including
upstream 4xx/network failures. Existing JWT/caller/correlation interceptors,
SimpleClientHttpRequestFactory connect/read timeouts and error translation remain.
Other managed JWKS HTTP clients may also expose standard client meters after use.

## Prometheus and Grafana

`observability/prometheus/prometheus.yml` scrapes the three stable DNS targets
`user-api:9091`, `learning-api:9091`, `jwks-api:9091`, every 15s with 5s timeout.
Per scrape: 20k sample limit, 20 labels/sample, bounded label-name/value sizes.
This avoids unbounded ingestion on accidental instrumentation changes; rejected
scrapes become DOWN and must be investigated. No self-scrape/extra backend is added.

Image `prom/prometheus:v3.13.5` is the explicitly versioned LTS release listed by
the [official download page](https://prometheus.io/download/). Runtime is non-root,
read-only root filesystem, capabilities dropped, 512 MiB memory, one CPU, 128 PID
limit, unless-stopped restart. `/prometheus` is the sole named writable volume
`springboot_project_prometheus_data`; config is read-only. Retention is 15 days or
2 GiB (flag `2GB`, reported by Prometheus as `2GiB`), whichever limit is reached first. Size retention is not a hard filesystem
quota: WAL/head/temporary compaction need extra disk. Backups/capacity/outage
hardening remain Phase 6. Readiness uses the image's wget and `/-/ready`.

Grafana provisioning adds UID `prometheus` at `http://prometheus:9090`, proxy mode,
15s interval, non-default/non-editable. Existing Loki and any existing manually
managed datasources are preserved. No new dashboards/alerts are created.

## Manual checks and PromQL

Run existing Compose with its project name and debug override as documented in
the verification report. UI: `http://localhost:9090/targets` (adjust host port).
API: `GET /api/v1/targets`; every target must be UP with no lastError.

```powershell
python observability/verify-baseline.py --runtime
python observability/verify-metrics.py --credentials observability/local-test-credentials.json
docker compose -p springboot_project exec -T prometheus promtool check config /etc/prometheus/prometheus.yml
docker compose -p springboot_project exec -T prometheus wget -q -O - http://jwks-api:9091/actuator/prometheus
```

The credentials file must already exist and be ignored; it contains an existing
account's `usernameOrEmail` and `password`. Never commit/print it. The verifier
marks authenticated checks NOT VERIFIED when absent; it does not create users.
It logs out its own refresh session. Raw metrics are safe by policy, but avoid
publishing the full exposition externally without review.

Useful queries (Grafana Explore -> Prometheus):

```promql
# Reachability and request rate
up{job="springboot"}
sum by (service) (rate(http_server_requests_seconds_count[5m]))
# 5xx error fraction; use status=~"4..|5.." for all rejected/failed requests
sum by (service) (rate(http_server_requests_seconds_count{status=~"5.."}[5m]))
 / clamp_min(sum by (service) (rate(http_server_requests_seconds_count[5m])), 0.000001)
# p95 seconds; replace 0.95 with 0.50 or 0.99
histogram_quantile(0.95, sum by (le,service) (rate(http_server_requests_seconds_bucket[5m])))
# Per-route p99
histogram_quantile(0.99, sum by (le,service,uri) (rate(http_server_requests_seconds_bucket[5m])))
# Internal client latency (when traffic exists)
histogram_quantile(0.95, sum by (le) (rate(http_client_requests_seconds_bucket{service="learning-api",uri="/internal/users/{id}"}[5m])))
# Security and pools
sum by (service,operation,result) (increase(app_security_events_total[15m]))
hikaricp_connections_active / hikaricp_connections_max
hikaricp_connections_pending
sum by (service,area) (jvm_memory_used_bytes)
```

For route-specific business latency, exclude health and scrape routes where
appropriate. Metrics endpoints are part of framework HTTP observations and may
contribute to service-wide rate/latency. Keep PromQL labels distinct from JSON log
fields (`http.route` in logs corresponds to `uri` in HTTP metrics).

Reference: [Spring HTTP observations](https://docs.spring.io/spring-framework/reference/integration/observability.html),
[Boot Actuator endpoints](https://docs.spring.io/spring-boot/reference/actuator/endpoints.html),
[Boot Tomcat factory](https://docs.spring.io/spring-boot/api/java/org/springframework/boot/tomcat/servlet/TomcatServletWebServerFactory.html).
Phase 3 adds SDK-owned tracing and its Collector/Tempo backend; see tracing.md.
Phase 2 itself adds no exporters pointing at nonexistent destinations, explicit
exemplar configuration or trace-label substitutes.
