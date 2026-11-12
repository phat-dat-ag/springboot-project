# Consolidated Phase 6 verification checklist

Current evidence: `phase6-20261112T031510Z-c66c0468`. Counts: `{"PASS": 750, "NOT VERIFIED": 10, "FAIL": 2, "NOT APPLICABLE": 2}`. A PASS applies to its stated scope; prior passes are not used as substitutes for current tests.

## Current executed checks and explicit gaps

| Status | Check | Detail |
| --- | --- | --- |
| PASS | baseline has exactly 16 jp_dev containers |  |
| PASS | target containers belong to this checkout |  |
| PASS | required target containers identified |  |
| PASS | fresh immutable baseline captured | container IDs/start times, volumes, protected fingerprints, Grafana state and existing backend availability |
| PASS | Docker Compose base/selected overrides validate |  |
| PASS | published ports loopback-only: fluent-bit |  |
| PASS | published ports loopback-only: fluent-bit-state-init |  |
| PASS | published ports loopback-only: flyway-mysql |  |
| PASS | published ports loopback-only: flyway-postgres |  |
| PASS | published ports loopback-only: grafana |  |
| PASS | published ports loopback-only: jwks-api |  |
| PASS | published ports loopback-only: learning-api |  |
| PASS | published ports loopback-only: loki |  |
| PASS | published ports loopback-only: mysql |  |
| PASS | published ports loopback-only: opensearch |  |
| PASS | published ports loopback-only: opensearch-dashboards |  |
| PASS | published ports loopback-only: otel-collector |  |
| PASS | published ports loopback-only: otel-queue-init |  |
| PASS | published ports loopback-only: postgres |  |
| PASS | published ports loopback-only: prometheus |  |
| PASS | published ports loopback-only: tempo |  |
| PASS | published ports loopback-only: tempo-storage-init |  |
| PASS | published ports loopback-only: user-api |  |
| PASS | internal telemetry endpoints unpublished: otel-collector |  |
| PASS | internal telemetry endpoints unpublished: tempo |  |
| PASS | internal telemetry endpoints unpublished: fluent-bit |  |
| PASS | 10% sampling: user-api |  |
| PASS | private metrics listener: user-api |  |
| PASS | read-only key mounts: user-api |  |
| PASS | 10% sampling: learning-api |  |
| PASS | private metrics listener: learning-api |  |
| PASS | read-only key mounts: learning-api |  |
| PASS | 10% sampling: jwks-api |  |
| PASS | private metrics listener: jwks-api |  |
| PASS | read-only key mounts: jwks-api |  |
| PASS | Prometheus configuration and recording rules |  |
| PASS | Prometheus idle/missing/histogram fixtures |  |
| PASS | Collector native configuration |  |
| PASS | Loki native configuration |  |
| PASS | Fluent Bit native dry-run |  |
| PASS | Tempo loaded config and 72h retention via supported status API |  |
| PASS | service readiness: user-api |  |
| PASS | public metrics endpoint denied: user-api |  |
| PASS | sensitive actuator endpoint protected: user-api |  |
| PASS | HTTP behavior: user-api probe 0 | expected 401, observed 401 |
| PASS | correlation preserved/generated: user-api |  |
| PASS | HTTP behavior: user-api probe 1 | expected 401, observed 401 |
| PASS | correlation preserved/generated: user-api |  |
| PASS | service readiness: learning-api |  |
| PASS | public metrics endpoint denied: learning-api |  |
| PASS | sensitive actuator endpoint protected: learning-api |  |
| PASS | HTTP behavior: learning-api probe 2 | expected 401, observed 401 |
| PASS | correlation preserved/generated: learning-api |  |
| PASS | HTTP behavior: learning-api probe 3 | expected 401, observed 401 |
| PASS | correlation preserved/generated: learning-api |  |
| PASS | service readiness: jwks-api |  |
| PASS | public metrics endpoint denied: jwks-api |  |
| PASS | sensitive actuator endpoint protected: jwks-api |  |
| PASS | HTTP behavior: jwks-api probe 4 | expected 200, observed 200 |
| PASS | correlation preserved/generated: jwks-api |  |
| PASS | HTTP behavior: jwks-api probe 5 | expected 200, observed 200 |
| PASS | correlation preserved/generated: jwks-api |  |
| PASS | HTTP behavior: user-api probe 6 | expected 200, observed 200 |
| PASS | correlation preserved/generated: user-api |  |
| PASS | access-token kid matches published RSA JWKS |  |
| PASS | access-token issuer matches configured contract |  |
| PASS | HTTP behavior: learning-api probe 7 | expected 200, observed 200 |
| PASS | correlation preserved/generated: learning-api |  |
| PASS | HTTP behavior: user-api probe 8 | expected 403, observed 403 |
| PASS | correlation preserved/generated: user-api |  |
| NOT VERIFIED | positive administrative User access | existing account lacks admin role; internal positive access is tested |
| PASS | HTTP behavior: user-api probe 9 | expected 401, observed 401 |
| PASS | correlation preserved/generated: user-api |  |
| PASS | HTTP behavior: user-api probe 10 | expected 403, observed 403 |
| PASS | correlation preserved/generated: user-api |  |
| PASS | HTTP behavior: learning-api probe 11 | expected 401, observed 401 |
| PASS | correlation preserved/generated: learning-api |  |
| PASS | HTTP behavior: learning-api probe 12 | expected 200, observed 200 |
| PASS | correlation preserved/generated: learning-api |  |
| PASS | Learning to User actual internal JWT communication |  |
| PASS | refresh rotates this verification session |  |
| PASS | HTTP behavior: learning-api probe 14 | expected 200, observed 200 |
| PASS | correlation preserved/generated: learning-api |  |
| PASS | verification session logout cleanup |  |
| PASS | request context isolation across independent live probes |  |
| PASS | one observed Loki HTTP completion: user-api |  |
| PASS | JSON schema fields: user-api |  |
| PASS | UTC timestamp parses: user-api |  |
| PASS | canonical log metadata: user-api |  |
| PASS | numeric final HTTP fields: user-api |  |
| PASS | independent correlation and W3C IDs: user-api |  |
| PASS | bounded route in logs: user-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: user-api |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: user-api |  |
| PASS | remote W3C parent continued: user-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: user-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: user-api |  |
| PASS | JSON schema fields: user-api |  |
| PASS | UTC timestamp parses: user-api |  |
| PASS | canonical log metadata: user-api |  |
| PASS | numeric final HTTP fields: user-api |  |
| PASS | independent correlation and W3C IDs: user-api |  |
| PASS | bounded route in logs: user-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: user-api |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: user-api |  |
| PASS | remote W3C parent continued: user-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: user-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: learning-api |  |
| PASS | JSON schema fields: learning-api |  |
| PASS | UTC timestamp parses: learning-api |  |
| PASS | canonical log metadata: learning-api |  |
| PASS | numeric final HTTP fields: learning-api |  |
| PASS | independent correlation and W3C IDs: learning-api |  |
| PASS | bounded route in logs: learning-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: learning-api |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: learning-api |  |
| PASS | remote W3C parent continued: learning-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: learning-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: learning-api |  |
| PASS | JSON schema fields: learning-api |  |
| PASS | UTC timestamp parses: learning-api |  |
| PASS | canonical log metadata: learning-api |  |
| PASS | numeric final HTTP fields: learning-api |  |
| PASS | independent correlation and W3C IDs: learning-api |  |
| PASS | bounded route in logs: learning-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: learning-api |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: learning-api |  |
| PASS | remote W3C parent continued: learning-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: learning-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: jwks-api |  |
| PASS | JSON schema fields: jwks-api |  |
| PASS | UTC timestamp parses: jwks-api |  |
| PASS | canonical log metadata: jwks-api |  |
| PASS | numeric final HTTP fields: jwks-api |  |
| PASS | independent correlation and W3C IDs: jwks-api |  |
| PASS | bounded route in logs: jwks-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: jwks-api |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: jwks-api |  |
| PASS | remote W3C parent continued: jwks-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: jwks-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: jwks-api |  |
| PASS | JSON schema fields: jwks-api |  |
| PASS | UTC timestamp parses: jwks-api |  |
| PASS | canonical log metadata: jwks-api |  |
| PASS | numeric final HTTP fields: jwks-api |  |
| PASS | independent correlation and W3C IDs: jwks-api |  |
| PASS | bounded route in logs: jwks-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: jwks-api |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: jwks-api |  |
| PASS | remote W3C parent continued: jwks-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: jwks-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: user-api |  |
| PASS | JSON schema fields: user-api |  |
| PASS | UTC timestamp parses: user-api |  |
| PASS | canonical log metadata: user-api |  |
| PASS | numeric final HTTP fields: user-api |  |
| PASS | independent correlation and W3C IDs: user-api |  |
| PASS | bounded route in logs: user-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: user-api |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: user-api |  |
| PASS | remote W3C parent continued: user-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: user-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: learning-api |  |
| PASS | JSON schema fields: learning-api |  |
| PASS | UTC timestamp parses: learning-api |  |
| PASS | canonical log metadata: learning-api |  |
| PASS | numeric final HTTP fields: learning-api |  |
| PASS | independent correlation and W3C IDs: learning-api |  |
| PASS | bounded route in logs: learning-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: learning-api |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: learning-api |  |
| PASS | remote W3C parent continued: learning-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: learning-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: user-api |  |
| PASS | JSON schema fields: user-api |  |
| PASS | UTC timestamp parses: user-api |  |
| PASS | canonical log metadata: user-api |  |
| PASS | numeric final HTTP fields: user-api |  |
| PASS | independent correlation and W3C IDs: user-api |  |
| PASS | bounded route in logs: user-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: user-api |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: user-api |  |
| PASS | remote W3C parent continued: user-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: user-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: user-api |  |
| PASS | JSON schema fields: user-api |  |
| PASS | UTC timestamp parses: user-api |  |
| PASS | canonical log metadata: user-api |  |
| PASS | numeric final HTTP fields: user-api |  |
| PASS | independent correlation and W3C IDs: user-api |  |
| PASS | bounded route in logs: user-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: user-api |  |
| PASS | trace environment resource |  |
| PASS | trace environment resource |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: user-api |  |
| PASS | remote W3C parent continued: user-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: user-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: user-api |  |
| PASS | JSON schema fields: user-api |  |
| PASS | UTC timestamp parses: user-api |  |
| PASS | canonical log metadata: user-api |  |
| PASS | numeric final HTTP fields: user-api |  |
| PASS | independent correlation and W3C IDs: user-api |  |
| PASS | bounded route in logs: user-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: user-api |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: user-api |  |
| PASS | remote W3C parent continued: user-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: user-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: learning-api |  |
| PASS | JSON schema fields: learning-api |  |
| PASS | UTC timestamp parses: learning-api |  |
| PASS | canonical log metadata: learning-api |  |
| PASS | numeric final HTTP fields: learning-api |  |
| PASS | independent correlation and W3C IDs: learning-api |  |
| PASS | bounded route in logs: learning-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: learning-api |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: learning-api |  |
| PASS | remote W3C parent continued: learning-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: learning-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: learning-api |  |
| PASS | JSON schema fields: learning-api |  |
| PASS | UTC timestamp parses: learning-api |  |
| PASS | canonical log metadata: learning-api |  |
| PASS | numeric final HTTP fields: learning-api |  |
| PASS | independent correlation and W3C IDs: learning-api |  |
| PASS | bounded route in logs: learning-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: learning-api |  |
| PASS | trace environment resource |  |
| PASS | trace environment resource |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: learning-api |  |
| PASS | Learning server to HTTP client to User parent chain |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: learning-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: user-api |  |
| PASS | JSON schema fields: user-api |  |
| PASS | UTC timestamp parses: user-api |  |
| PASS | canonical log metadata: user-api |  |
| PASS | numeric final HTTP fields: user-api |  |
| PASS | independent correlation and W3C IDs: user-api |  |
| PASS | bounded route in logs: user-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: user-api |  |
| PASS | trace environment resource |  |
| PASS | trace environment resource |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: user-api |  |
| PASS | Learning server to HTTP client to User parent chain |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: user-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | one observed Loki HTTP completion: learning-api |  |
| PASS | JSON schema fields: learning-api |  |
| PASS | UTC timestamp parses: learning-api |  |
| PASS | canonical log metadata: learning-api |  |
| PASS | numeric final HTTP fields: learning-api |  |
| PASS | independent correlation and W3C IDs: learning-api |  |
| PASS | bounded route in logs: learning-api |  |
| PASS | same event identity/fields in Loki and OpenSearch: learning-api |  |
| PASS | trace environment resource |  |
| PASS | stored server span timing/log identity: learning-api |  |
| PASS | remote W3C parent continued: learning-api |  |
| PASS | tested credentials/tokens/identity absent from stored telemetry: learning-api |  |
| PASS | sensitive span attribute names absent |  |
| PASS | all nine Prometheus targets UP without scrape errors |  |
| PASS | no tested secrets or sensitive labels in live exposition: user-api |  |
| PASS | no tested secrets or sensitive labels in live exposition: learning-api |  |
| PASS | no tested secrets or sensitive labels in live exposition: jwks-api |  |
| PASS | actual metric across three services: http_server_requests_seconds_count |  |
| PASS | actual metric across three services: http_server_requests_seconds_bucket |  |
| PASS | actual metric across three services: jvm_memory_used_bytes |  |
| PASS | actual metric across three services: jvm_gc_pause_seconds_count |  |
| PASS | actual metric across three services: jvm_threads_live_threads |  |
| PASS | actual metric across three services: process_cpu_usage |  |
| PASS | actual metric across three services: app_security_events_total |  |
| PASS | finite HTTP histogram percentile 0.5 |  |
| PASS | finite HTTP histogram percentile 0.95 |  |
| PASS | finite HTTP histogram percentile 0.99 |  |
| PASS | database-only metric: hikaricp_connections_active |  |
| PASS | database-only metric: hikaricp_connections_pending |  |
| PASS | database-only metric: hikaricp_connections_max |  |
| PASS | database-only metric: hikaricp_connections_acquire_seconds_count |  |
| PASS | database-only metric: hikaricp_connections_timeout_total |  |
| PASS | collected infrastructure metric: otelcol_exporter_queue_size |  |
| PASS | collected infrastructure metric: otelcol_exporter_queue_capacity |  |
| PASS | collected infrastructure metric: otelcol_exporter_send_failed_spans |  |
| PASS | collected infrastructure metric: fluentbit_output_errors_total |  |
| PASS | collected infrastructure metric: fluentbit_output_dropped_records_total |  |
| PASS | actual internal HTTP client metric |  |
| PASS | five recording rules loaded and healthy |  |
| PASS | provisioned stable UID/folder: sb5-overview |  |
| PASS | variables/time range: sb5-overview |  |
| PASS | service/environment variables: sb5-overview |  |
| PASS | units/legends/no-data/options: sb5-overview/Reading this dashboard |  |
| PASS | units/legends/no-data/options: sb5-overview/Service availability |  |
| PASS | datasource resolves: Service availability |  |
| PASS | service filter output: Service availability |  |
| PASS | units/legends/no-data/options: sb5-overview/HTTP requests per second |  |
| PASS | datasource resolves: HTTP requests per second |  |
| PASS | service filter output: HTTP requests per second |  |
| PASS | units/legends/no-data/options: sb5-overview/HTTP 4xx per second |  |
| PASS | datasource resolves: HTTP 4xx per second |  |
| PASS | service filter output: HTTP 4xx per second |  |
| PASS | units/legends/no-data/options: sb5-overview/HTTP 5xx per second |  |
| PASS | datasource resolves: HTTP 5xx per second |  |
| PASS | service filter output: HTTP 5xx per second |  |
| PASS | units/legends/no-data/options: sb5-overview/HTTP error percentage |  |
| PASS | datasource resolves: HTTP error percentage |  |
| PASS | service filter output: HTTP error percentage |  |
| PASS | units/legends/no-data/options: sb5-overview/HTTP p50 latency |  |
| PASS | datasource resolves: HTTP p50 latency |  |
| PASS | service filter output: HTTP p50 latency |  |
| PASS | units/legends/no-data/options: sb5-overview/HTTP p95 latency |  |
| PASS | datasource resolves: HTTP p95 latency |  |
| PASS | service filter output: HTTP p95 latency |  |
| PASS | units/legends/no-data/options: sb5-overview/HTTP p99 latency |  |
| PASS | datasource resolves: HTTP p99 latency |  |
| PASS | service filter output: HTTP p99 latency |  |
| PASS | units/legends/no-data/options: sb5-overview/Request volume over selected range |  |
| PASS | datasource resolves: Request volume over selected range |  |
| PASS | service filter output: Request volume over selected range |  |
| PASS | units/legends/no-data/options: sb5-overview/Recent application errors |  |
| PASS | datasource resolves: Recent application errors |  |
| PASS | service filter output: Recent application errors |  |
| PASS | units/legends/no-data/options: sb5-overview/JVM memory used |  |
| PASS | datasource resolves: JVM memory used |  |
| PASS | service filter output: JVM memory used |  |
| PASS | units/legends/no-data/options: sb5-overview/Process CPU |  |
| PASS | datasource resolves: Process CPU |  |
| PASS | service filter output: Process CPU |  |
| PASS | units/legends/no-data/options: sb5-overview/Application uptime |  |
| PASS | datasource resolves: Application uptime |  |
| PASS | service filter output: Application uptime |  |
| PASS | provisioned stable UID/folder: sb5-http |  |
| PASS | variables/time range: sb5-http |  |
| PASS | service/environment variables: sb5-http |  |
| PASS | units/legends/no-data/options: sb5-http/Throughput by service |  |
| PASS | datasource resolves: Throughput by service |  |
| PASS | service filter output: Throughput by service |  |
| PASS | units/legends/no-data/options: sb5-http/Top routes by throughput |  |
| PASS | datasource resolves: Top routes by throughput |  |
| PASS | service filter output: Top routes by throughput |  |
| PASS | units/legends/no-data/options: sb5-http/HTTP method breakdown |  |
| PASS | datasource resolves: HTTP method breakdown |  |
| PASS | service filter output: HTTP method breakdown |  |
| PASS | units/legends/no-data/options: sb5-http/Status distribution |  |
| PASS | datasource resolves: Status distribution |  |
| PASS | service filter output: Status distribution |  |
| PASS | units/legends/no-data/options: sb5-http/4xx trend |  |
| PASS | datasource resolves: 4xx trend |  |
| PASS | service filter output: 4xx trend |  |
| PASS | units/legends/no-data/options: sb5-http/5xx trend |  |
| PASS | datasource resolves: 5xx trend |  |
| PASS | service filter output: 5xx trend |  |
| PASS | units/legends/no-data/options: sb5-http/HTTP error ratio |  |
| PASS | datasource resolves: HTTP error ratio |  |
| PASS | service filter output: HTTP error ratio |  |
| PASS | units/legends/no-data/options: sb5-http/p50 latency |  |
| PASS | datasource resolves: p50 latency |  |
| PASS | service filter output: p50 latency |  |
| PASS | units/legends/no-data/options: sb5-http/p95 latency |  |
| PASS | datasource resolves: p95 latency |  |
| PASS | service filter output: p95 latency |  |
| PASS | units/legends/no-data/options: sb5-http/p99 latency |  |
| PASS | datasource resolves: p99 latency |  |
| PASS | service filter output: p99 latency |  |
| PASS | units/legends/no-data/options: sb5-http/Slow endpoints by p95 |  |
| PASS | datasource resolves: Slow endpoints by p95 |  |
| PASS | service filter output: Slow endpoints by p95 |  |
| PASS | units/legends/no-data/options: sb5-http/Request duration distribution |  |
| PASS | datasource resolves: Request duration distribution |  |
| PASS | service filter output: Request duration distribution |  |
| PASS | units/legends/no-data/options: sb5-http/Internal HTTP client throughput |  |
| PASS | datasource resolves: Internal HTTP client throughput |  |
| PASS | service filter output: Internal HTTP client throughput |  |
| PASS | units/legends/no-data/options: sb5-http/Internal HTTP client p95 |  |
| PASS | datasource resolves: Internal HTTP client p95 |  |
| PASS | service filter output: Internal HTTP client p95 |  |
| PASS | provisioned stable UID/folder: sb5-jvm |  |
| PASS | variables/time range: sb5-jvm |  |
| PASS | service/environment variables: sb5-jvm |  |
| PASS | units/legends/no-data/options: sb5-jvm/Heap used |  |
| PASS | datasource resolves: Heap used |  |
| PASS | service filter output: Heap used |  |
| PASS | units/legends/no-data/options: sb5-jvm/Heap maximum |  |
| PASS | datasource resolves: Heap maximum |  |
| PASS | service filter output: Heap maximum |  |
| PASS | units/legends/no-data/options: sb5-jvm/Heap utilization |  |
| PASS | datasource resolves: Heap utilization |  |
| PASS | service filter output: Heap utilization |  |
| PASS | units/legends/no-data/options: sb5-jvm/Non-heap memory |  |
| PASS | datasource resolves: Non-heap memory |  |
| PASS | service filter output: Non-heap memory |  |
| PASS | units/legends/no-data/options: sb5-jvm/GC frequency |  |
| PASS | datasource resolves: GC frequency |  |
| PASS | service filter output: GC frequency |  |
| PASS | units/legends/no-data/options: sb5-jvm/GC pause time per second |  |
| PASS | datasource resolves: GC pause time per second |  |
| PASS | service filter output: GC pause time per second |  |
| PASS | units/legends/no-data/options: sb5-jvm/Mean GC pause |  |
| PASS | datasource resolves: Mean GC pause |  |
| PASS | service filter output: Mean GC pause |  |
| PASS | units/legends/no-data/options: sb5-jvm/Live threads |  |
| PASS | datasource resolves: Live threads |  |
| PASS | service filter output: Live threads |  |
| PASS | units/legends/no-data/options: sb5-jvm/Daemon threads |  |
| PASS | datasource resolves: Daemon threads |  |
| PASS | service filter output: Daemon threads |  |
| PASS | units/legends/no-data/options: sb5-jvm/Process CPU |  |
| PASS | datasource resolves: Process CPU |  |
| PASS | service filter output: Process CPU |  |
| PASS | units/legends/no-data/options: sb5-jvm/System CPU |  |
| PASS | datasource resolves: System CPU |  |
| PASS | service filter output: System CPU |  |
| PASS | units/legends/no-data/options: sb5-jvm/Process uptime |  |
| PASS | datasource resolves: Process uptime |  |
| PASS | service filter output: Process uptime |  |
| PASS | units/legends/no-data/options: sb5-jvm/Executor active threads |  |
| PASS | datasource resolves: Executor active threads |  |
| PASS | service filter output: Executor active threads |  |
| PASS | units/legends/no-data/options: sb5-jvm/Executor maximum threads |  |
| PASS | datasource resolves: Executor maximum threads |  |
| PASS | service filter output: Executor maximum threads |  |
| PASS | units/legends/no-data/options: sb5-jvm/Executor pool size |  |
| PASS | datasource resolves: Executor pool size |  |
| PASS | service filter output: Executor pool size |  |
| PASS | units/legends/no-data/options: sb5-jvm/Executor queued tasks |  |
| PASS | datasource resolves: Executor queued tasks |  |
| PASS | service filter output: Executor queued tasks |  |
| PASS | units/legends/no-data/options: sb5-jvm/Open file descriptors |  |
| PASS | datasource resolves: Open file descriptors |  |
| PASS | service filter output: Open file descriptors |  |
| PASS | units/legends/no-data/options: sb5-jvm/JVM direct/mapped buffer memory |  |
| PASS | datasource resolves: JVM direct/mapped buffer memory |  |
| PASS | service filter output: JVM direct/mapped buffer memory |  |
| PASS | provisioned stable UID/folder: sb5-database |  |
| PASS | variables/time range: sb5-database |  |
| PASS | service/environment variables: sb5-database |  |
| PASS | units/legends/no-data/options: sb5-database/Active connections |  |
| PASS | datasource resolves: Active connections |  |
| PASS | service filter output: Active connections |  |
| PASS | units/legends/no-data/options: sb5-database/Idle connections |  |
| PASS | datasource resolves: Idle connections |  |
| PASS | service filter output: Idle connections |  |
| PASS | units/legends/no-data/options: sb5-database/Pending connections |  |
| PASS | datasource resolves: Pending connections |  |
| PASS | service filter output: Pending connections |  |
| PASS | units/legends/no-data/options: sb5-database/Maximum connections |  |
| PASS | datasource resolves: Maximum connections |  |
| PASS | service filter output: Maximum connections |  |
| PASS | units/legends/no-data/options: sb5-database/Pool utilization |  |
| PASS | datasource resolves: Pool utilization |  |
| PASS | service filter output: Pool utilization |  |
| PASS | units/legends/no-data/options: sb5-database/Mean connection acquisition latency |  |
| PASS | datasource resolves: Mean connection acquisition latency |  |
| PASS | service filter output: Mean connection acquisition latency |  |
| PASS | units/legends/no-data/options: sb5-database/Connection timeouts |  |
| PASS | datasource resolves: Connection timeouts |  |
| PASS | service filter output: Connection timeouts |  |
| PASS | units/legends/no-data/options: sb5-database/Pool acquisition maximum |  |
| PASS | datasource resolves: Pool acquisition maximum |  |
| PASS | service filter output: Pool acquisition maximum |  |
| PASS | provisioned stable UID/folder: sb5-security |  |
| PASS | variables/time range: sb5-security |  |
| PASS | service/environment variables: sb5-security |  |
| PASS | units/legends/no-data/options: sb5-security/Security event meaning |  |
| PASS | units/legends/no-data/options: sb5-security/Authentication failures |  |
| PASS | datasource resolves: Authentication failures |  |
| PASS | service filter output: Authentication failures |  |
| PASS | units/legends/no-data/options: sb5-security/Authorization denials |  |
| PASS | datasource resolves: Authorization denials |  |
| PASS | service filter output: Authorization denials |  |
| PASS | units/legends/no-data/options: sb5-security/Security event trends |  |
| PASS | datasource resolves: Security event trends |  |
| PASS | service filter output: Security event trends |  |
| PASS | units/legends/no-data/options: sb5-security/Security events over selected range |  |
| PASS | datasource resolves: Security events over selected range |  |
| PASS | service filter output: Security events over selected range |  |
| PASS | units/legends/no-data/options: sb5-security/HTTP 401 trend |  |
| PASS | datasource resolves: HTTP 401 trend |  |
| PASS | service filter output: HTTP 401 trend |  |
| PASS | units/legends/no-data/options: sb5-security/HTTP 403 trend |  |
| PASS | datasource resolves: HTTP 403 trend |  |
| PASS | service filter output: HTTP 403 trend |  |
| PASS | units/legends/no-data/options: sb5-security/Authentication and authorization logs |  |
| PASS | datasource resolves: Authentication and authorization logs |  |
| PASS | service filter output: Authentication and authorization logs |  |
| PASS | provisioned stable UID/folder: sb5-logging |  |
| PASS | variables/time range: sb5-logging |  |
| PASS | service/environment variables: sb5-logging |  |
| PASS | units/legends/no-data/options: sb5-logging/Log investigation |  |
| PASS | units/legends/no-data/options: sb5-logging/Log volume by service |  |
| PASS | datasource resolves: Log volume by service |  |
| PASS | service filter output: Log volume by service |  |
| PASS | units/legends/no-data/options: sb5-logging/Log volume by severity |  |
| PASS | datasource resolves: Log volume by severity |  |
| PASS | service filter output: Log volume by severity |  |
| PASS | units/legends/no-data/options: sb5-logging/ERROR trend |  |
| PASS | datasource resolves: ERROR trend |  |
| PASS | service filter output: ERROR trend |  |
| PASS | units/legends/no-data/options: sb5-logging/WARN trend |  |
| PASS | datasource resolves: WARN trend |  |
| PASS | service filter output: WARN trend |  |
| PASS | units/legends/no-data/options: sb5-logging/Recent errors |  |
| PASS | datasource resolves: Recent errors |  |
| PASS | service filter output: Recent errors |  |
| PASS | units/legends/no-data/options: sb5-logging/Recent warnings |  |
| PASS | datasource resolves: Recent warnings |  |
| PASS | service filter output: Recent warnings |  |
| PASS | units/legends/no-data/options: sb5-logging/HTTP request failures |  |
| PASS | datasource resolves: HTTP request failures |  |
| PASS | service filter output: HTTP request failures |  |
| PASS | units/legends/no-data/options: sb5-logging/Correlated logs |  |
| PASS | datasource resolves: Correlated logs |  |
| PASS | service filter output: Correlated logs |  |
| PASS | provisioned stable UID/folder: sb5-tracing |  |
| PASS | variables/time range: sb5-tracing |  |
| PASS | service/environment variables: sb5-tracing |  |
| PASS | units/legends/no-data/options: sb5-tracing/Trace investigation workflow |  |
| PASS | units/legends/no-data/options: sb5-tracing/Service p95 |  |
| PASS | datasource resolves: Service p95 |  |
| PASS | service filter output: Service p95 |  |
| PASS | units/legends/no-data/options: sb5-tracing/Service p99 |  |
| PASS | datasource resolves: Service p99 |  |
| PASS | service filter output: Service p99 |  |
| PASS | units/legends/no-data/options: sb5-tracing/Request throughput |  |
| PASS | datasource resolves: Request throughput |  |
| PASS | service filter output: Request throughput |  |
| PASS | units/legends/no-data/options: sb5-tracing/Recent errors with trace navigation |  |
| PASS | datasource resolves: Recent errors with trace navigation |  |
| PASS | service filter output: Recent errors with trace navigation |  |
| PASS | provisioned stable UID/folder: sb5-infrastructure |  |
| PASS | variables/time range: sb5-infrastructure |  |
| PASS | service/environment variables: sb5-infrastructure |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Coverage and limitations |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/All scrape target health |  |
| PASS | datasource resolves: All scrape target health |  |
| PASS | service filter output: All scrape target health |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Scrape duration |  |
| PASS | datasource resolves: Scrape duration |  |
| PASS | service filter output: Scrape duration |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Collector queue utilization |  |
| PASS | datasource resolves: Collector queue utilization |  |
| PASS | service filter output: Collector queue utilization |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Collector failed span export attempts |  |
| PASS | datasource resolves: Collector failed span export attempts |  |
| PASS | service filter output: Collector failed span export attempts |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Collector refused spans |  |
| PASS | datasource resolves: Collector refused spans |  |
| PASS | service filter output: Collector refused spans |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Fluent Bit output errors |  |
| PASS | datasource resolves: Fluent Bit output errors |  |
| PASS | service filter output: Fluent Bit output errors |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Fluent Bit dropped records |  |
| PASS | datasource resolves: Fluent Bit dropped records |  |
| PASS | service filter output: Fluent Bit dropped records |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Fluent Bit failed retries |  |
| PASS | datasource resolves: Fluent Bit failed retries |  |
| PASS | service filter output: Fluent Bit failed retries |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Loki received lines |  |
| PASS | datasource resolves: Loki received lines |  |
| PASS | service filter output: Loki received lines |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Loki flush failures |  |
| PASS | datasource resolves: Loki flush failures |  |
| PASS | service filter output: Loki flush failures |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Loki WAL bytes |  |
| PASS | datasource resolves: Loki WAL bytes |  |
| PASS | service filter output: Loki WAL bytes |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Tempo received spans |  |
| PASS | datasource resolves: Tempo received spans |  |
| PASS | service filter output: Tempo received spans |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Tempo failed flushes |  |
| PASS | datasource resolves: Tempo failed flushes |  |
| PASS | service filter output: Tempo failed flushes |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Grafana alert instances |  |
| PASS | datasource resolves: Grafana alert instances |  |
| PASS | service filter output: Grafana alert instances |  |
| PASS | units/legends/no-data/options: sb5-infrastructure/Prometheus resident memory |  |
| PASS | datasource resolves: Prometheus resident memory |  |
| PASS | service filter output: Prometheus resident memory |  |
| PASS | 21 unique Grafana alert rules loaded |  |
| PASS | alert thresholds/labels/evaluation behavior: ServiceDown |  |
| PASS | muted grouped routing: ServiceDown |  |
| PASS | alert thresholds/labels/evaluation behavior: MissingMetricsUser |  |
| PASS | muted grouped routing: MissingMetricsUser |  |
| PASS | alert thresholds/labels/evaluation behavior: MissingMetricsLearning |  |
| PASS | muted grouped routing: MissingMetricsLearning |  |
| PASS | alert thresholds/labels/evaluation behavior: MissingMetricsJWKS |  |
| PASS | muted grouped routing: MissingMetricsJWKS |  |
| PASS | alert thresholds/labels/evaluation behavior: High5xxErrorRate |  |
| PASS | muted grouped routing: High5xxErrorRate |  |
| PASS | alert thresholds/labels/evaluation behavior: HighHTTPErrorRatio |  |
| PASS | muted grouped routing: HighHTTPErrorRatio |  |
| PASS | alert thresholds/labels/evaluation behavior: HighP95Latency |  |
| PASS | muted grouped routing: HighP95Latency |  |
| PASS | alert thresholds/labels/evaluation behavior: HighP99Latency |  |
| PASS | muted grouped routing: HighP99Latency |  |
| PASS | alert thresholds/labels/evaluation behavior: HighHeapUsage |  |
| PASS | muted grouped routing: HighHeapUsage |  |
| PASS | alert thresholds/labels/evaluation behavior: HighCPUUsage |  |
| PASS | muted grouped routing: HighCPUUsage |  |
| PASS | alert thresholds/labels/evaluation behavior: ExcessiveGCPause |  |
| PASS | muted grouped routing: ExcessiveGCPause |  |
| PASS | alert thresholds/labels/evaluation behavior: HikariPoolSaturation |  |
| PASS | muted grouped routing: HikariPoolSaturation |  |
| PASS | alert thresholds/labels/evaluation behavior: HikariPendingConnections |  |
| PASS | muted grouped routing: HikariPendingConnections |  |
| PASS | alert thresholds/labels/evaluation behavior: CollectorExportFailures |  |
| PASS | muted grouped routing: CollectorExportFailures |  |
| PASS | alert thresholds/labels/evaluation behavior: CollectorQueueSaturation |  |
| PASS | muted grouped routing: CollectorQueueSaturation |  |
| PASS | alert thresholds/labels/evaluation behavior: FluentBitDeliveryFailures |  |
| PASS | muted grouped routing: FluentBitDeliveryFailures |  |
| PASS | alert thresholds/labels/evaluation behavior: LokiIngestionFailures |  |
| PASS | muted grouped routing: LokiIngestionFailures |  |
| PASS | alert thresholds/labels/evaluation behavior: TempoUnavailable |  |
| PASS | muted grouped routing: TempoUnavailable |  |
| PASS | alert thresholds/labels/evaluation behavior: PrometheusTargetDown |  |
| PASS | muted grouped routing: PrometheusTargetDown |  |
| PASS | alert thresholds/labels/evaluation behavior: ElevatedAuthenticationFailures |  |
| PASS | muted grouped routing: ElevatedAuthenticationFailures |  |
| PASS | alert thresholds/labels/evaluation behavior: ElevatedAuthorizationDenials |  |
| PASS | muted grouped routing: ElevatedAuthorizationDenials |  |
| PASS | all-day notification mute remains active |  |
| PASS | all 21 Grafana rules evaluated successfully |  |
| PASS | non-persisted Grafana alert preview: normal |  |
| PASS | non-persisted Grafana alert preview: breach |  |
| PASS | non-persisted Grafana alert preview: no-data |  |
| PASS | non-persisted execution-error preview |  |
| PASS | existing log-to-trace derived field retained |  |
| PASS | trace-to-log query returns actual events |  |
| PASS | derived log trace link extracts actual trace |  |
| PASS | Tempo TraceQL exploration query accepted |  |
| PASS | Tempo TraceQL exploration query accepted |  |
| PASS | Tempo TraceQL exploration query accepted |  |
| PASS | Grafana authentication required |  |
| PASS | Collector internal readiness |  |
| PASS | Tempo internal readiness |  |
| PASS | Loki internal readiness |  |
| PASS | Fluent Bit current-process exhausted retries/dropped records zero |  |
| PASS | persistent buffering/retention contract: fluent-bit/fluent-bit.conf |  |
| PASS | persistent buffering/retention contract: otel-collector/config.yml |  |
| PASS | persistent buffering/retention contract: loki/loki-config.yml |  |
| PASS | persistent buffering/retention contract: tempo/tempo.yml |  |
| PASS | OpenSearch application indices healthy |  |
| PASS | OpenSearch 30-day lifecycle configured |  |
| PASS | dated OpenSearch indices actively assigned lifecycle |  |
| PASS | bounded resource/queue/ingestion snapshot captured | development observation only; no representative production load |
| PASS | effective 10m/3 Docker log rotation on 11 services |  |
| FAIL | production telemetry access-control readiness | OpenSearch security disabled; Loki/Tempo/Collector/Prometheus trust internal plaintext network; loopback exposure is not production authentication |
| NOT VERIFIED | browser rendering and navigation | no browser automation available; API coverage only |
| NOT VERIFIED | elapsed Pending/Firing/Resolved lifecycle | preview-only; isolated timed rule plan is in Phase 6B |
| NOT VERIFIED | external notification delivery/recovery | forbidden in Phase 6A; mute remains active |
| NOT VERIFIED | crash durability and queue/buffer overflow | no live failure injection; historical restart evidence is not crash proof |
| NOT VERIFIED | physical retention deletion | policy/configuration checked, no expiration forced or deletion observed |
| NOT VERIFIED | backup integrity and restore | no restore rehearsal performed; repository state inspected |
| NOT VERIFIED | production load capacity | single bounded development snapshot, not representative load |
| NOT VERIFIED | runtime async endpoints | no public production async fixture; Maven integration tests provide isolated coverage |
| NOT VERIFIED | backend storage pressure alerting | reliable collected capacity metric/alert source absent |
| FAIL | lossless compressed-rollover collection | immediate gzip archive + exact-current-file tails can lose unread history while Fluent Bit is stopped; mitigation/test plan documented |
| NOT APPLICABLE | JWKS database pool | JWKS has no datasource |
| NOT APPLICABLE | Tempo service graphs/span-derived metrics | not enabled; no second metrics pipeline required |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-jwks-api-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-user-api-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-learning-api-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-grafana-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-prometheus-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-fluent-bit-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-opensearch-dashboards-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-loki-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-tempo-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-opensearch-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-otel-collector-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-otel-queue-init-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-tempo-storage-init-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-frontend-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-fluent-bit-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-vocabulary-api-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-opensearch-dashboards-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-jwks-api-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-user-api-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-opensearch-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-logs-ui-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-logging-ui-init-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-logging-init-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-flyway-mysql-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-flyway-postgres-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-fluent-bit-state-init-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-postgres-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /springboot_project-mysql-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-gateway-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-flyway-user-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-flyway-vocabulary-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-sqlserver-init-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-mysql-1 |  |
| PASS | container identity/start/mounts/ports unchanged: /jp_dev-sqlserver-1 |  |
| PASS | all original volumes retained, no new persistent volumes |  |
| PASS | environment/key/credential fingerprints unchanged |  |
| PASS | effective Compose configuration unchanged |  |
| PASS | deployed config file unchanged: observability\loki\loki-config.yml |  |
| PASS | deployed config file unchanged: observability\otel-collector\config.yml |  |
| PASS | deployed config file unchanged: observability\prometheus\prometheus.yml |  |
| PASS | deployed config file unchanged: observability\tempo\tempo.yml |  |
| PASS | deployed config file unchanged: observability\grafana\provisioning\dashboards\application-logs.yml |  |
| PASS | deployed config file unchanged: observability\grafana\provisioning\datasources\loki.yml |  |
| PASS | deployed config file unchanged: observability\grafana\provisioning\datasources\prometheus.yml |  |
| PASS | deployed config file unchanged: observability\grafana\provisioning\datasources\tempo.yml |  |
| PASS | deployed config file unchanged: observability\fluent-bit\fluent-bit.conf |  |
| PASS | deployed config file unchanged: observability\fluent-bit\parsers.conf |  |
| PASS | deployed config file unchanged: observability\grafana\phase5-inventory.json |  |
| PASS | deployed config file unchanged: observability\grafana\dashboards\application-logs.json |  |
| PASS | deployed config file unchanged: observability\grafana\dashboards\database.json |  |
| PASS | deployed config file unchanged: observability\grafana\dashboards\http.json |  |
| PASS | deployed config file unchanged: observability\grafana\dashboards\infrastructure.json |  |
| PASS | deployed config file unchanged: observability\grafana\dashboards\jvm.json |  |
| PASS | deployed config file unchanged: observability\grafana\dashboards\logging.json |  |
| PASS | deployed config file unchanged: observability\grafana\dashboards\overview.json |  |
| PASS | deployed config file unchanged: observability\grafana\dashboards\security.json |  |
| PASS | deployed config file unchanged: observability\grafana\dashboards\tracing.json |  |
| PASS | deployed config file unchanged: observability\grafana\provisioning\alerting\phase5.json |  |
| PASS | Grafana contacts unchanged |  |
| PASS | Grafana policies unchanged |  |
| PASS | Grafana alerts unchanged |  |
| PASS | Grafana datasources unchanged |  |
| PASS | Grafana dashboard unchanged: springboot-application-logs |  |
| PASS | Grafana dashboard unchanged: sb5-logging |  |
| PASS | Grafana dashboard unchanged: sb5-database |  |
| PASS | Grafana dashboard unchanged: sb5-tracing |  |
| PASS | Grafana dashboard unchanged: sb5-http |  |
| PASS | Grafana dashboard unchanged: sb5-jvm |  |
| PASS | Grafana dashboard unchanged: sb5-overview |  |
| PASS | Grafana dashboard unchanged: sb5-infrastructure |  |
| PASS | Grafana dashboard unchanged: sb5-security |  |
| PASS | public JWKS body unchanged: /api/v1/jwks/user |  |
| PASS | public JWKS body unchanged: /api/v1/jwks/learning |  |
| PASS | Git HEAD/branch unchanged: . |  |
| PASS | Git HEAD/branch unchanged: springboot-user-api |  |
| PASS | submodule worktree unchanged: springboot-user-api |  |
| PASS | Git HEAD/branch unchanged: springboot-learning-api |  |
| PASS | submodule worktree unchanged: springboot-learning-api |  |
| PASS | Git HEAD/branch unchanged: springboot-jwks-api |  |
| PASS | submodule worktree unchanged: springboot-jwks-api |  |

## Historical acceptance inventory

These rows are transcribed from prior reports, including superseded/history rows. They are historical claims, not new Phase 6 evidence. Phase 3 later authenticated checks supersede its earlier credential gaps; Phase 4 persistent queues supersede Phase 3 RAM-only configuration. Current criteria above determine this assessment.

| Report | Historical status | Criterion |
| --- | --- | --- |
| [phase0-baseline.md](phase0-baseline.md) | PASS | `docker compose -p springboot_project --env-file .env -f docker-compose.yml config --quiet` |
| [phase0-baseline.md](phase0-baseline.md) | PASS | `docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml config --quiet` |
| [phase0-baseline.md](phase0-baseline.md) | PASS | `git diff --check` in all four repositories |
| [phase0-baseline.md](phase0-baseline.md) | PASS | Inspect all modules, runtime/env/infra and dependency compatibility |
| [phase0-baseline.md](phase0-baseline.md) | PASS | Preserve existing canonical service identities and routing |
| [phase0-baseline.md](phase0-baseline.md) | PASS | Apply version/environment metadata and safe configuration defaults |
| [phase0-baseline.md](phase0-baseline.md) | PASS | Define all required request/resource concepts without premature filter migration |
| [phase0-baseline.md](phase0-baseline.md) | PASS | No destinationless exporter enabled by new defaults |
| [phase0-baseline.md](phase0-baseline.md) | PASS | No newly public sensitive Actuator endpoints |
| [phase0-baseline.md](phase0-baseline.md) | PASS | Preserve networks, volumes, ports and runtime containers |
| [phase0-baseline.md](phase0-baseline.md) | NOT VERIFIED | New metadata/collector config active in deployed images/processes |
| [phase0-baseline.md](phase0-baseline.md) | PASS | Real secrets/env files/deployment keys untouched; no commit/branch changes |
| [phase1-verification.md](phase1-verification.md) | PASS | User |
| [phase1-verification.md](phase1-verification.md) | PASS | Learning |
| [phase1-verification.md](phase1-verification.md) | PASS | JWKS |
| [phase1-verification.md](phase1-verification.md) | PASS | Valid/malformed/oversized correlation ID response behavior |
| [phase1-verification.md](phase1-verification.md) | PASS | Exactly one final completion with numeric status/duration for the checked requests |
| [phase1-verification.md](phase1-verification.md) | PASS | No tested credentials/token/body/header/query/path sentinels in captured logs |
| [phase1-verification.md](phase1-verification.md) | PASS | Health-check INFO suppression |
| [phase1-verification.md](phase1-verification.md) | PASS | Inspect/preserve existing pipeline and Phase 0 identity |
| [phase1-verification.md](phase1-verification.md) | PASS | Consistent JSON schema/types and optional real tracing MDC |
| [phase1-verification.md](phase1-verification.md) | PASS | Validated/returned/propagated correlation ID and MDC cleanup |
| [phase1-verification.md](phase1-verification.md) | PASS | Final HTTP success/4xx/5xx lifecycle including security/async/errors |
| [phase1-verification.md](phase1-verification.md) | NOT VERIFIED | Deployed non-admin 403 behavior/logging |
| [phase1-verification.md](phase1-verification.md) | PASS | Safe business severity and sensitive-data regression protection |
| [phase1-verification.md](phase1-verification.md) | PASS | Collector JSON/timestamp parsing and both destinations |
| [phase1-verification.md](phase1-verification.md) | PASS | Safe downstream historical field migration |
| [phase1-verification.md](phase1-verification.md) | PASS | All three relevant Maven suites |
| [phase1-verification.md](phase1-verification.md) | PASS | Safe deployment and preservation |
| [phase1-verification.md](phase1-verification.md) | PASS | Existing auth/JWKS/internal JWT compatibility |
| [phase1-verification.md](phase1-verification.md) | PASS | Unexpected OTLP errors absent in checked window |
| [phase1-verification.md](phase1-verification.md) | PASS | Documentation and phase boundaries |
| [phase1-verification.md](phase1-verification.md) | PASS | No commit/push/reset/branch change or unrelated repository modifications |
| [phase2-verification.md](phase2-verification.md) | PASS | User |
| [phase2-verification.md](phase2-verification.md) | PASS | Learning |
| [phase2-verification.md](phase2-verification.md) | PASS | JWKS |
| [phase2-verification.md](phase2-verification.md) | PASS | Total |
| [phase2-verification.md](phase2-verification.md) | PASS | Inspect/preserve Phase0/1 implementation |
| [phase2-verification.md](phase2-verification.md) | PASS | Uniform Micrometer/Prometheus identity/naming |
| [phase2-verification.md](phase2-verification.md) | PASS | HTTP count/status/outcome/duration and aggregatable histograms |
| [phase2-verification.md](phase2-verification.md) | PASS | JVM/process/system and supported executors |
| [phase2-verification.md](phase2-verification.md) | PASS | Hikari/JDBC where applicable |
| [phase2-verification.md](phase2-verification.md) | PASS | Bounded security metrics without double counting |
| [phase2-verification.md](phase2-verification.md) | PASS | Learning -> User client instrumentation |
| [phase2-verification.md](phase2-verification.md) | NOT VERIFIED | Deployed authenticated Learning -> User client/JWT/correlation |
| [phase2-verification.md](phase2-verification.md) | NOT VERIFIED | Successful deployed login/logout/refresh |
| [phase2-verification.md](phase2-verification.md) | PASS | Secure scrape exposure, health/API rules preserved |
| [phase2-verification.md](phase2-verification.md) | PASS | Prometheus deployment/storage/retention/health |
| [phase2-verification.md](phase2-verification.md) | PASS | Grafana datasource/query integration |
| [phase2-verification.md](phase2-verification.md) | PASS | Existing logs/correlation/trace metadata protected |
| [phase2-verification.md](phase2-verification.md) | PASS | JWKS consumer compatibility and jp_dev preservation |
| [phase2-verification.md](phase2-verification.md) | PASS | Tests without weakened/skipped regressions |
| [phase2-verification.md](phase2-verification.md) | PASS | No unexpected OTLP export errors/Phase3–6 work |
| [phase2-verification.md](phase2-verification.md) | PASS | Documentation and safe Git behavior |
| [phase3-verification.md](phase3-verification.md) | PASS | 1. Inspect six documents, real versions/clients/security/Compose and Git |
| [phase3-verification.md](phase3-verification.md) | PASS | 2. Boot-supported single tracing architecture; preserve metrics/logs |
| [phase3-verification.md](phase3-verification.md) | PASS | 3. Instrument incoming HTTP in all services; IDs/names/durations/status |
| [phase3-verification.md](phase3-verification.md) | PASS | 3. Supported outgoing managed clients; metadata/privacy/no duplicates |
| [phase3-verification.md](phase3-verification.md) | PASS | 4. W3C valid/missing/invalid parent and tracestate |
| [phase3-verification.md](phase3-verification.md) | PASS | 4. Independent validated correlation and MDC completion behavior |
| [phase3-verification.md](phase3-verification.md) | PASS | 5. Learning -> User server/client/server parenting and correlation in tests |
| [phase3-verification.md](phase3-verification.md) | PASS | 5. Deployed authenticated Learning -> User same trace and JWT success |
| [phase3-verification.md](phase3-verification.md) | PASS | 5. Timeouts, JWT and error handling preserved |
| [phase3-verification.md](phase3-verification.md) | PASS | 6. JSON traceId/spanId/correlationId, no duplicate fields/events |
| [phase3-verification.md](phase3-verification.md) | PASS | 6. Async/error/security behavior and MDC cleanup |
| [phase3-verification.md](phase3-verification.md) | PASS | 7. Environment sampling,0/1 controls,parent-based policy |
| [phase3-verification.md](phase3-verification.md) | PASS | 8. Pinned Collector, limiter/batch/retry/queue/health/internal constraints |
| [phase3-verification.md](phase3-verification.md) | PASS | 9. Pinned Tempo, storage/retention/readiness/resources/internal access |
| [phase3-verification.md](phase3-verification.md) | PASS | 9. Ordinary restart trace persistence |
| [phase3-verification.md](phase3-verification.md) | NOT VERIFIED | 9. Crash durability / retention deletion |
| [phase3-verification.md](phase3-verification.md) | PASS | 10. Grafana datasource query, existing sources and real-field links |
| [phase3-verification.md](phase3-verification.md) | NOT VERIFIED | 10. Browser navigation click |
| [phase3-verification.md](phase3-verification.md) | PASS | 11. Sensitive-data protections and low-cardinality templates |
| [phase3-verification.md](phase3-verification.md) | PASS | 12. JWKS cross-project compatibility |
| [phase3-verification.md](phase3-verification.md) | PASS | 13. Existing logging/metrics/scrape pipelines preserved |
| [phase3-verification.md](phase3-verification.md) | PASS | 14. Relevant Maven suites and exact counts |
| [phase3-verification.md](phase3-verification.md) | PASS | 15.1Ã¢â‚¬â€œ12. Compose/build/deploy/health/scrapes/Collector/Tempo/Grafana |
| [phase3-verification.md](phase3-verification.md) | PASS | 15.13Ã¢â‚¬â€œ14. Real trace delivery and all three server spans |
| [phase3-verification.md](phase3-verification.md) | PASS | 15.15-17. Live Learning -> User parents/common trace/correlation |
| [phase3-verification.md](phase3-verification.md) | PASS | 15.18Ã¢â‚¬â€œ19. JSON IDs plus Loki/OpenSearch ingestion |
| [phase3-verification.md](phase3-verification.md) | PASS | 15.20. Positive deployed login/refresh/logout/internal JWT |
| [phase3-verification.md](phase3-verification.md) | PASS | 15.21. Deployed JWKS response compatibility |
| [phase3-verification.md](phase3-verification.md) | PASS | 15.22Ã¢â‚¬â€œ23. No exporter errors in observed window/unrelated preservation |
| [phase3-verification.md](phase3-verification.md) | PASS | 16. Documentation, commands, limitations and future dependencies |
| [phase3-verification.md](phase3-verification.md) | PASS | 17. Git/data/key safety; no commits/push/unrelated repo changes |
| [phase3-verification.md](phase3-verification.md) | PASS | Phase3 critical acceptance |
| [phase3-verification.md](phase3-verification.md) | PASS | 1a. Successful User API login |
| [phase3-verification.md](phase3-verification.md) | PASS | 1b. Successful User API refresh |
| [phase3-verification.md](phase3-verification.md) | PASS | 1c. Successful User API logout |
| [phase3-verification.md](phase3-verification.md) | PASS | 2. Authenticated Learning -> User internal JWT communication |
| [phase3-verification.md](phase3-verification.md) | PASS | 3. W3C traceparent propagation across Learning -> User |
| [phase3-verification.md](phase3-verification.md) | PASS | 4. Server/client/server parent-child relationships |
| [phase3-verification.md](phase3-verification.md) | PASS | 5. Shared trace ID across Learning and User |
| [phase3-verification.md](phase3-verification.md) | PASS | 6. Independent, preserved X-Correlation-ID |
| [phase3-verification.md](phase3-verification.md) | PASS | 7. Trace visibility in Tempo using Grafana datasource queries |
| [phase3-verification.md](phase3-verification.md) | PASS | 8. Matching traceId/spanId/correlationId in Loki and OpenSearch |
| [phase3-verification.md](phase3-verification.md) | PASS | 9. No actual verification secrets/PII in observed logs/exported spans |
| [phase3-verification.md](phase3-verification.md) | PASS | 10. All APIs and observability services remain operational |
| [phase4-verification.md](phase4-verification.md) | PASS | Loki |
| [phase4-verification.md](phase4-verification.md) | PASS | OpenSearch |
| [phase4-verification.md](phase4-verification.md) | PASS | Tempo |
| [phase4-verification.md](phase4-verification.md) | PASS | Baseline inventory/config/volumes/protected hashes |
| [phase4-verification.md](phase4-verification.md) | PASS | Filesystem buffering, bounded independent outputs |
| [phase4-verification.md](phase4-verification.md) | PASS | Tail DB/restart/rename/truncate/compressed exclusion |
| [phase4-verification.md](phase4-verification.md) | NOT VERIFIED | Rotation+compression during collector downtime |
| [phase4-verification.md](phase4-verification.md) | PASS | Loki persistent storage/retention settings/limits |
| [phase4-verification.md](phase4-verification.md) | NOT VERIFIED | Loki physical expiry deletion |
| [phase4-verification.md](phase4-verification.md) | PASS | OpenSearch replica investigation/narrow new-index ISM/mappings |
| [phase4-verification.md](phase4-verification.md) | NOT VERIFIED | OpenSearch physical expiry deletion |
| [phase4-verification.md](phase4-verification.md) | PASS | Bounded effective Docker logging on11 main containers |
| [phase4-verification.md](phase4-verification.md) | PASS | Persistent Collector queue/retry/restart recovery |
| [phase4-verification.md](phase4-verification.md) | NOT VERIFIED | Queue overflow/disk-full/crash behavior |
| [phase4-verification.md](phase4-verification.md) | PASS | Tempo persistence/retention/query/restart |
| [phase4-verification.md](phase4-verification.md) | NOT VERIFIED | Tempo physical expiry deletion |
| [phase4-verification.md](phase4-verification.md) | PASS | Prometheus persistence/targets/metrics/histograms |
| [phase4-verification.md](phase4-verification.md) | PASS | Auth/JWT/JWKS/tracing/correlation/privacy regression |
| [phase4-verification.md](phase4-verification.md) | PASS | Datasources/fresh logs/fresh traces/API health |
| [phase4-verification.md](phase4-verification.md) | PASS | Endpoint/security/key/env preservation |
| [phase4-verification.md](phase4-verification.md) | PASS | Maven regression |
| [phase4-verification.md](phase4-verification.md) | PASS | jp_dev/unrelated containers unchanged |
| [phase4-verification.md](phase4-verification.md) | NOT VERIFIED | Hard quotas/HA/backup-restore/production capacity |
| [phase5-verification.md](phase5-verification.md) | PASS | 1 Baseline inspection / actual versions |
| [phase5-verification.md](phase5-verification.md) | PASS | 2 Deployment safety / persistent data |
| [phase5-verification.md](phase5-verification.md) | PASS | 3 Version-controlled stable provisioning |
| [phase5-verification.md](phase5-verification.md) | PASS | 4 Overview |
| [phase5-verification.md](phase5-verification.md) | PASS | 5 HTTP |
| [phase5-verification.md](phase5-verification.md) | PASS | 6 JVM/runtime |
| [phase5-verification.md](phase5-verification.md) | PASS | 7 Database/pools |
| [phase5-verification.md](phase5-verification.md) | PASS | 8 Security |
| [phase5-verification.md](phase5-verification.md) | PASS | 9 Logging |
| [phase5-verification.md](phase5-verification.md) | PASS | 10 Tracing query/search/navigation paths |
| [phase5-verification.md](phase5-verification.md) | NOT VERIFIED | 10 Browser clicks/rendering |
| [phase5-verification.md](phase5-verification.md) | PASS | 11 Infrastructure metrics |
| [phase5-verification.md](phase5-verification.md) | PASS | 12 Recording rules |
| [phase5-verification.md](phase5-verification.md) | PASS | 13–14 Unified alert provisioning / supported alerts |
| [phase5-verification.md](phase5-verification.md) | NOT VERIFIED | 14 Unsupported capacity/OpenSearch/buffer/token alerts |
| [phase5-verification.md](phase5-verification.md) | PASS | 15–16 Internal evaluation / safe routing |
| [phase5-verification.md](phase5-verification.md) | NOT VERIFIED | 15 External delivery / recovery notifications |
| [phase5-verification.md](phase5-verification.md) | NOT VERIFIED | 16 Live elapsed pending/firing/recovery transition |
| [phase5-verification.md](phase5-verification.md) | PASS | 17 Security/privacy |
| [phase5-verification.md](phase5-verification.md) | PASS | 18 Automated validation |
| [phase5-verification.md](phase5-verification.md) | PASS | 19 Runtime deploy / health / persistence / unrelated containers |
| [phase5-verification.md](phase5-verification.md) | PASS | 20 Phase0–4 regression |
| [phase5-verification.md](phase5-verification.md) | PASS | 21 Cross-project compatibility |
| [phase5-verification.md](phase5-verification.md) | PASS | 22 Documentation / environment operations |
| [phase5-verification.md](phase5-verification.md) | PASS | 23 Git constraints |
| [phase5-verification.md](phase5-verification.md) | PASS | 24 Final verification and limitations |
| [phase5-verification.md](phase5-verification.md) | NOT VERIFIED | Production paging acceptance |

## Dated remediation delta — 2026-11-12

The original checklist is historical. [Follow-up evidence](phase6a-remediation.md) changes only the narrower compression cause, not general durability or production security.

| Follow-up criterion | Status | Evidence |
|---|---|---|
| Endpoint/socket/exposure inventory | PASS | `remediation-endpoints.json`, `telemetry-security.md` |
| Loopback host access/private ingestion preserved | PASS | Fresh runtime regression/publications |
| Authenticated/encrypted production telemetry live | FAIL | Existing plaintext network/OpenSearch security disabled |
| Secure configuration and OpenSearch migration preparation | IMPLEMENTED BUT NOT DEPLOYED | `secure-production/`; structural validation only |
| Stable-name bounded spool deployed on all three APIs | PASS | Loaded external XML plus real files/source events |
| Isolated rollover/downtime/DB reuse/restart | PASS |12 checks,52 events per protocol sink |
| Legacy gzip untouched, tail DB not reset | PASS | Isolated legacy hash and migration; original live state mounts retained |
| Real Loki/OpenSearch delivery and trace propagation | PASS |15 matched events and linked trace |
| Global exactly-once/crash/overflow durability | NOT VERIFIED | No guarantee asserted; Phase6B remains gated |
| Original volumes/keys/Grafana/JWKS/jp_dev preservation | PASS | Independent comparison against pre-change baseline |
| Production readiness overall | FAIL | Security failure plus outstanding recovery/capacity/notification evidence |
