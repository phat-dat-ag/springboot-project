# Observability baseline and standards

Phase 5 dashboards and Grafana Unified Alerting are now deployed. Start with
[dashboard operations](dashboards.md), [alerting operations](alerting.md) and
[Phase 5 verification](phase5-verification.md). Evaluation is active; external
notification delivery remains muted and NOT VERIFIED. Complete panel and rule
inventories are in [dashboard-inventory.md](dashboard-inventory.md) and
[alert-rules.md](alert-rules.md). Phase 6 is not implemented.

Phase 0 establishes configuration and identity, not production readiness. Start
with [the verification record](phase0-baseline.md) for what was actually checked
and [the phase plan](phase-plan.md) for acceptance gates. Backend-specific usage
remains in [Grafana](grafana/README.md) and [OpenSearch](opensearch/README.md).

The subsequent deployment and live authentication/ingestion checks are recorded
in [Phase 0 runtime verification](phase0-runtime-verification.md).

Phase 1's current contract is [structured logging](structured-logging.md), with
test and deployment evidence in [Phase 1 verification](phase1-verification.md).
Phase 2 metrics and security are documented in [metrics.md](metrics.md), with
[Phase 2 verification](phase2-verification.md).
Phase 3 tracing configuration is in [tracing.md](tracing.md), with actual test,
deployment evidence and remaining acceptance gaps in [Phase 3 verification](phase3-verification.md).
Phase 4 adds bounded persistent collection and trace queues, safe new-index
retention and Docker log rotation. See [logging pipeline operations](logging-pipeline.md)
and [Phase 4 deployment/recovery evidence](phase4-verification.md). These describe
development hardening and its remaining production acceptance limits.

## Current and target architecture

Current: SLF4J -> Logback JSON console + rolling file -> shared application log
volumes -> Fluent Bit -> Loki/Grafana and OpenSearch/Dashboards. Micrometer local
instrumentation exists in all APIs. Phase 2 adds Prometheus scraping and a Grafana
metrics datasource. Phase 3 adds the Boot-managed OTel tracing starter to all APIs,
OTLP traces through Collector to persistent Tempo, and a Grafana Tempo datasource.
File logging is not OTLP; no OTLP metrics/logs pipeline is enabled.

Target, completed across the implementation phases: consistent structured application logs with
safe correlation -> durable collection -> log storage; Micrometer -> Prometheus
-> Grafana; Micrometer Tracing/OTel -> OTel Collector -> Tempo -> Grafana. Keep
the current log path until a tested migration is approved. Decide whether both
log stores remain necessary; no backend is removed in Phase 0.

## Canonical identity

| API | Canonical `service.name` / Spring application name | Compose DNS | Log filename |
| --- | --- | --- | --- |
| User | `user-learning` | `user-api` | `user-api.log` |
| Learning | `learning-api` | `learning-api` | `learning-api.log` |
| JWKS | `jwks-service` | `jwks-api` | `jwks-api.log` |

These deliberately preserve existing Loki labels and indexed records. Historical
documentation sometimes called User `user`; query `user-learning` for this stack.
JWT issuer/subject names identify authentication contracts, not observability
resources; do not rename them to match this table.

| Concept | Configuration source | JSON field | OTel resource attribute |
| --- | --- | --- | --- |
| Service identity | `spring.application.name` / `SPRING_APPLICATION_NAME` | `service` | `service.name` |
| Release version | `app.version` / `APP_VERSION`, otherwise Maven `project.version` | `serviceVersion` | `service.version` |
| Deployment environment | `app.deployment-environment` / `DEPLOYMENT_ENVIRONMENT`, default `development` | `environment` | `deployment.environment.name` |

`deployment.environment` is the conceptual/legacy name; current OTel semantic
conventions use [`deployment.environment.name`](https://opentelemetry.io/docs/specs/semconv/resource/deployment-environment/).
Do not emit both OTel attributes. JSON fields are application fields, not a claim
that an SDK exported them. The `management.opentelemetry.resource-attributes[...]`
map is ready for services with the OTel integration; it has no export effect by
itself. No second service-name variable or `OTEL_SERVICE_NAME` is introduced.

Use bounded, nonsecret values: names `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`; release
versions use the same characters up to 128 characters. Environments are
`development`, `test`, `staging`, `production`. Do not put URLs, tokens, usernames,
customer IDs, quotes or arbitrary JSON into metadata. Phase 0 documents these
constraints. Phase 1 encoder setters replace unsafe metadata with `unknown` rather
than interpolating it into raw JSON.

`APP_NAME` controls the file basename, not `service.name`. Keep current basenames
until Fluent Bit paths are migrated together. Do not put request/trace IDs into
Loki labels or meter tags. `serviceVersion` remains in the log body, not a label.

## JSON request-event contract

Phase 1 is implemented; see [structured logging](structured-logging.md) for lifecycle,
privacy, compatibility, and [verification evidence](phase1-verification.md).

Phase 0 introduced stable metadata. Phase 1 centralizes safe encoding and request
lifecycle logging. Legacy records are retained; new events use the current schema:

| Concept | Historical Phase 0 JSON | Current JSON | Type / rule |
| --- | --- | --- | --- |
| Correlation | `correlationId` | `correlationId` | Validated opaque string |
| Trace | `traceId` | `traceId` | Instrumentation-owned 32 lowercase hex characters |
| Span | `spanId` | `spanId` | Instrumentation-owned 16 lowercase hex characters |
| HTTP method | `httpMethod` | `http.request.method` | Bounded method or `OTHER` |
| Route | `uri` | `http.route` | Matched route template or `UNMATCHED`, never raw sensitive paths |
| HTTP status | `status` | `http.response.status_code` | Integer |
| Elapsed time | `elapsed_ms` | `durationMs` | Nonnegative number measured with a monotonic clock |
| Outcome | Absent | `outcome` | `success` (1xx-3xx), `client_error` (4xx), `server_error` (5xx), otherwise `unknown` |

`durationMs` and `outcome` are application-log conventions, not OTel resource
attributes or replacements for native metric/span units/status. Route/method/status
names follow HTTP semantic concepts. In particular, a 4xx server response does
not automatically imply an OTel error span: follow the instrumentation convention.
Do not fill absent trace IDs with UUIDs, `unknown`, or the correlation ID.
Phase 1 preserves historical fields and indexes and uses new numeric field names.
The default Discover columns are migrated without overwriting personal customizations.
There are no contradictory aliases or in-place changes to old field types.

## Correlation and trace-context standard

Correlation/MDC rules are implemented in Phase 1; SDK tracing is configured in Phase 3:

1. Accept exactly one `X-Correlation-ID` matching
   `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`. Reject ambiguous duplicate, blank,
   oversized/control-character values by replacing them with a new UUID. Do not
   reject the business request solely because a diagnostic ID is malformed.
2. Put the chosen ID in MDC before security and return it on the response,
   including rejected requests where a response can be written. Propagate the
   same ID through managed outgoing clients; generate one for a background call
   only when there is no valid current ID.
3. Scope and restore MDC on normal, error and async execution. No pooled-thread
   leakage; asynchronous tasks require explicit context propagation. Do not clear
   another scope's tracing fields indiscriminately.
4. Correlation IDs are caller-controlled diagnostics, never authenticated identity,
   authorization evidence or proof that requests belong to the same trusted user.
5. Let tracing instrumentation validate, extract and inject W3C `traceparent` and
   `tracestate`. Do not hand-build trace headers, blindly copy untrusted raw values,
   or treat JWKS's `callerTraceId`/`callerSpanId` diagnostics as SDK spans.
6. Maintain distinct correlation and trace identities. One trace has multiple
   spans; the receiver creates its own server span rather than reusing the sender's
   span ID. Never put secrets or PII in diagnostic headers or baggage.

All three services now accept validated incoming correlation IDs. Caller interceptors
propagate them and leave SDK-owned trace headers alone. User internal
and external JWKS retrieval both use the metadata interceptor. Phase 3 configures
SDK tracing across the HTTP boundary; see Phase 3 evidence for live verification limits.

## Configuration conventions

Root `.env` supplies Compose interpolation; `.env.<service>` supplies service
container variables. Module `.env.example` documents standalone JVM settings.
Spring Boot does not load `.env` files automatically. Compose `environment` wins
over service `env_file`; shell values win over root `.env` interpolation.

| Variable | Effective property / policy |
| --- | --- |
| `SPRING_APPLICATION_NAME` | Existing canonical Spring identity; configure per-service only if deliberately migrating |
| `APP_VERSION` | Optional release override; default is build version, not a copied fixed Compose version |
| `DEPLOYMENT_ENVIRONMENT` | Shared root Compose value, default `development`, supplied to APIs and Fluent Bit |
| `APP_NAME`, `APP_LOG_DIR` | Existing filename/path conventions; volumes and collector paths must agree |
| `LOG_LEVEL` | Standalone root logger; Compose retains existing `LOG_LEVEL`, `LEARNING_API_LOG_LEVEL`, `JWKS_API_LOG_LEVEL` mapping |
| `MANAGEMENT_METRICS_ENABLE_ALL` | `management.metrics.enable.all`, default true; Prometheus collects enabled meters in Phase 2 |
| `MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE` | Health standalone; Compose health,prometheus with private port protection; never `*` |
| `MANAGEMENT_TRACING_ENABLED` | `management.tracing.enabled`, default true; requires tracing dependencies |
| `MANAGEMENT_TRACING_SAMPLING_PROBABILITY` | All APIs default 0.1; Compose maps `TRACING_SAMPLING_PROBABILITY`, also default 0.1 |
| `MANAGEMENT_OTLP_METRICS_EXPORT_ENABLED` | `management.otlp.metrics.export.enabled`, default false |
| `MANAGEMENT_TRACING_EXPORT_OTLP_ENABLED` | `management.tracing.export.otlp.enabled`, false standalone; true in Compose |
| `MANAGEMENT_LOGGING_EXPORT_OTLP_ENABLED` | `management.logging.export.otlp.enabled`, default false |

Phase 3 replaces User's old 1.0 default with a uniform parent-based 0.1 budget.
Use 1.0 only for controlled development verification. Do not add a
configurable correlation-header name now: all existing consumers use the fixed
`X-Correlation-ID`, and an unused flag would imply support that does not exist.

Trace destination is supplied internally by Compose; metrics/log destinations remain absent:

| Signal setting | Supported Boot 4.1 property / direct environment spelling |
| --- | --- |
| Trace OTLP destination | `management.opentelemetry.tracing.export.otlp.endpoint` / `MANAGEMENT_OPENTELEMETRY_TRACING_EXPORT_OTLP_ENDPOINT` |
| Trace transport | `management.opentelemetry.tracing.export.otlp.transport` / `MANAGEMENT_OPENTELEMETRY_TRACING_EXPORT_OTLP_TRANSPORT` (`http` or `grpc`) |
| Log OTLP destination | `management.opentelemetry.logging.export.otlp.endpoint` / `MANAGEMENT_OPENTELEMETRY_LOGGING_EXPORT_OTLP_ENDPOINT` |
| Log transport | `management.opentelemetry.logging.export.otlp.transport` / `MANAGEMENT_OPENTELEMETRY_LOGGING_EXPORT_OTLP_TRANSPORT` |
| Micrometer OTLP metrics destination | `management.otlp.metrics.export.url` / `MANAGEMENT_OTLP_METRICS_EXPORT_URL` (HTTP/protobuf) |

Use Collector service DNS rather than `localhost` inside
containers. HTTP signal endpoints use `/v1/traces`, `/v1/metrics`, `/v1/logs`;
gRPC uses the configured gRPC endpoint without those HTTP paths. Typical ports
4318/4317 are now private tracing receiver ports; see tracing.md for exact transports.
Prometheus scrape/registry is implemented in Phase 2; Tempo datasource is Phase 3. Do not
enable native `OTEL_*` SDK autoconfiguration alongside Boot properties without
documenting precedence; it can contradict this baseline. Do not enable SDK metrics
and a Micrometer exporter for the same instruments unintentionally.

## Dependency compatibility

There is no root Maven aggregator or parent POM. Each submodule has an independent
Spring Boot parent, Java 17 target and Maven Wrapper. Do not run a root Maven build.

| Component | User | Learning | JWKS |
| --- | --- | --- | --- |
| Spring Boot parent | 4.1.1 | 4.1.2 | 4.1.2 |
| Java target | 17 | 17 | 17 |
| Docker build/runtime JDK | 21 / 21 | 21 / 21 | 17 / 17 |
| Logstash encoder | 8.1 | 8.1 | 8.1 |
| Logback from resolved test classpaths | 1.5.38 | 1.5.38 | 1.5.38 |
| Micrometer Core | 1.17.1 | 1.17.2 | 1.17.2 |
| Actuator | Present | Present | Present |
| Micrometer Tracing / OTel bridge | 1.7.1 / present | 1.7.2 / present | 1.7.2 / present |
| OTel API/SDK/exporter | 1.62.0, managed starter | 1.62.0, managed starter | 1.62.0, managed starter |
| OTLP metrics registry | 1.17.1, disabled | Absent | Absent |
| Prometheus registry | 1.17.1 (Phase 2) | 1.17.2 (Phase 2) | 1.17.2 (Phase 2) |

Source: each module's `pom.xml`, existing resolved test-report classpaths, and
cached Boot-published configuration metadata. These are build evidence, not an
inventory of deployed jars. No dependency/Java/Boot upgrades are made in Phase 0.
Boot manages framework versions; avoid hand-pinning a bridge/SDK independently.
Logstash encoder 8.1 uses Jackson 2; User also explicitly includes Jackson 2
compatibility dependencies. Do not remove these without focused compatibility tests.
Optional DevTools in Learning/JWKS is not telemetry. The two log stores duplicate
storage by design today; evaluate the operational need later, not through removal now.

## Docker, security and operations

Use the Compose project whose config path belongs to this checkout. The observed
project is `springboot_project`; `jp_dev` points at a separate repository. Never
reuse its name or network here. Run `python observability/verify-baseline.py --runtime`
for read-only detection and checks, or pass `--project` explicitly when not running.

Phase 0 adds a shared deployment environment; Phase 1 also mounts the custom JSON
parser read-only into Fluent Bit. Native Fluent Bit `${DEPLOYMENT_ENVIRONMENT}` interpolation fills
missing record environments; the Loki label reads `$environment`. Existing log
fields remain authoritative. If launching Fluent Bit outside Compose, supply that
variable explicitly. Collector configuration requires deliberate reload/recreation;
changing a mounted file alone does not prove its new config is loaded. The Phase 1
deployment and parser dry-run are recorded in the verification report.

Existing ports, DNS names, networks, persistent volumes, log/state mounts, restart policies,
health checks, resource limits and debug-override settings are preserved. Phase 3
adds internal tracing services and a new Tempo volume; see tracing.md. Phase 1
rebuilt/recreated only the three APIs and recreated Fluent Bit to load the parser.

Keep health as the only public Actuator capability. Phase 2 metrics use a private
unpublished listener and deny the scrape path on the application port; never expose `env`, `configprops`, heap
dumps or unrestricted management endpoints. Diagnostic metadata is untrusted.
Never log credentials, Authorization values, JWTs, key contents, rejected secrets
or whole environment/configuration dumps. JSON escaping is not redaction.

Phase 1 removes the known sensitive business logging and unsafe request paths/
throwable messages. Remaining gaps include the credential-dependent deployed
Learning -> User tracing acceptance gate (see Phase 3 evidence), no durable
collector outage queue, no repository-defined OpenSearch retention, Docker
`json-file` without per-container rotation options, no alerting, and single-node
unauthenticated development storage. Existing Loki 720h retention and Logback
100MB/30-day/2GB archive rules are unchanged; deletion enforcement is not verified.

Do not use destructive Docker commands, reset submodules, regenerate deployment
keys, or export expanded Compose models to a report. The verifier captures models
in memory and prints only allowlisted summaries; it does not write credentials.
