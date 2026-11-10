# Phase acceptance gates

This is the working scope for Phases 0-6. Later phases require separate review;
documenting an acceptance gate does not authorize implementing it in Phase 0.

| Phase | Scope | Acceptance evidence |
| --- | --- | --- |
| 0 — Baseline | Identity, safe defaults, dependency/configuration standards, runtime inventory | All module regression/binding tests pass; base/debug Compose validates under actual project; no new exporters/backends; ports/storage untouched; known runtime gaps explicit |
| 1 — Logging and correlation | Safe consistent request events, MDC/async lifecycle, correlation across HTTP calls | One validated ID follows Learning -> User; duplicate/unsafe incoming IDs replaced; 401/403/404/5xx and async completion covered once at final status; secrets absent; request schema/index/query migration tested |
| 2 — Metrics | Registry, secured exposure, Prometheus collection/storage, useful HTTP/JVM/pool/business instrumentation | All applicable targets scraped; rate/error/duration and pool metrics queryable; bounded tags/histograms; no public sensitive endpoints; data remains in storage after app restart |
| 3 — Tracing | Uniform Micrometer-to-OTel instrumentation, W3C propagation, initial trace destination | Real Learning -> User trace has common trace ID and correct parent/client/server relationships; SDK-owned IDs in logs; malformed context and background/async calls tested; explicit sampling budget and no orphan exporter errors |
| 4 — Collection | OTel Collector deployment and explicit signal routing, endpoint/transport/TLS/auth conventions | Health and export verified; traces routed to Tempo; no duplicate metrics/log ingestion; receiver disabled/unreachable behavior tested; existing file pipeline retained until approved replacement |
| 5 — Operations view | Grafana metrics/traces/log navigation, dashboards, alerts and runbooks | Datasources provisioned; one incident can be followed across signals; useful latency/error/saturation and ingestion alerts tested; credentials absent from provisioning |
| 6 — Production hardening | Durable queues, retention/rollover, access controls, capacity, load/outage/restore validation | Bounded disk and cardinality; controlled backend outage recovery; retention deletion and backup/restore verified; production authentication/TLS and least privilege; operational SLO evidence |

If Phase 3 requires the Collector before Phase 4, approve a minimal receiver as
part of that phase rather than pointing exporters at nonexistent infrastructure.
Prometheus, Tempo, Collector, dashboards, alerting and retention overhaul are not
part of the Phase 0 implementation.
