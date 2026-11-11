# Phase 3 tracing contract and operations

Spring HTTP observations -> Micrometer Tracing -> OpenTelemetry SDK -> OTLP
HTTP/protobuf (`otel-collector:4318/v1/traces`) -> Collector -> OTLP gRPC
(`tempo:4317`) -> Tempo local storage -> Grafana Tempo datasource (`tempo`).
See [verification evidence](phase3-verification.md) for actual results and gaps.

## Instrumentation and compatibility

All three modules use the Boot-managed `spring-boot-starter-opentelemetry`.
User already had it (Boot 4.1.1); Learning/JWKS add it (Boot 4.1.2). The managed
Micrometer OTel bridge is the only bridge; no Java agent, Sleuth, Brave, native
OTel SDK auto-configuration or parallel HTTP instrumentation is installed.
Java targets, Boot versions, authentication and endpoint contracts stay unchanged.
The existing Maven target is Java 17; User/Learning images run Java 21 and JWKS
runs Java 17. This phase does not perform a Java migration.

Boot servlet observations create SERVER spans and managed `RestClient.Builder` /
`RestTemplateBuilder` create CLIENT spans. Learning's existing `ServiceClientConfig`
already clones the managed builder, preserves the `/internal/users/{id}` template,
connect/read timeouts, caller/correlation interceptor, service JWT interceptor and
error translation. No client architecture change is required. JWKS has no current
production outgoing client; its client starter is test-scoped only.

TracingConfiguration supplies a DefaultTracingObservationHandler that skips
only child spans for spring.security.* contexts, retaining the enclosing span
for meter exemplars and asynchronous context restoration. Security observations and their framework
metrics remain enabled; HTTP spans own the request trace and a managed client
is a direct child of the server span. Authentication and HTTP observations remain. Async MVC work
uses Boot's `spring.task.execution.propagate-context=true`; arbitrary unmanaged
executors still require explicit context capture and restoration.

Resources retain `service.name=user-learning|learning-api|jwks-service`,
`service.version=${app.version}` (build version unless `APP_VERSION` overrides),
and `deployment.environment.name=${app.deployment-environment}`. No duplicate
legacy environment attribute is introduced. SDK metadata is also supplied by OTel.

## Context and logging

Only W3C propagation is configured. The SDK validates `traceparent`, continues a
valid parent, and starts a new trace for an invalid/missing parent. `tracestate`
continues with valid context. These diagnostics are never authenticated identity.
No arbitrary request headers are copied. Baggage propagation and baggage-to-MDC correlation are explicitly disabled
with management.tracing.baggage.enabled=false and correlation.enabled=false;
remote/correlation fields are also empty: do not add account, email, token, or other sensitive baggage.

The expected relationship is Learning SERVER -> Learning CLIENT -> User SERVER.
All share one trace ID; each span has its own ID. User's parent is the client span,
not the original Learning server span. JWKS key retrieval can add further client /
server spans when a decoder actually fetches keys; cached retrieval creates no HTTP call.

`X-Correlation-ID` is independent: existing validation, response header, propagation,
MDC scoping and once-only HTTP completion remain in the Phase 1 implementation.
JSON `traceId`/`spanId` are existing allowlisted, SDK-owned MDC fields; no duplicate
MDC provider or fabricated UUID tracing fields are added. Existing filter capture
and restoration preserve tracing context during completion/error/async handling.
Logs can have valid trace IDs for unsampled requests whose traces are never stored.
Existing optional API envelope meta.traceId can also be populated from SDK MDC;
no response field, endpoint or raw public JWKS key document is redesigned.

## Sampling

Standalone root probability defaults to **0.1** in all three services. Compose
uses root `TRACING_SAMPLING_PROBABILITY`, default **0.1**, mapped to each application's
`MANAGEMENT_TRACING_SAMPLING_PROBABILITY`. Set a value in [0,1]; lower the budget
for production based on measured volume/cost. `management.opentelemetry.tracing.sampler`
is explicitly `parent-based-trace-id-ratio`: valid sampled parents remain sampled
and unsampled parents remain unsampled, independent of local root probability.
This honors upstream tracing decisions; public clients can influence sampling.
Ingress trust/rate controls and capacity review remain deployment responsibilities.

For controlled development verification only, set the process environment:

```powershell
$env:TRACING_SAMPLING_PROBABILITY = '1.0'
# Recreate only the three APIs using the existing base/debug Compose command.
# Remove this override and recreate them afterward to restore the normal budget.
Remove-Item Env:TRACING_SAMPLING_PROBABILITY
```

The verifier instead sends valid sampled remote parents to deterministic diagnostic
requests; it does not change the deployed root budget. Below 100%, not every request
has a stored trace; successful export still depends on pipeline availability.
Sampling never changes application business behavior or authentication.

Standalone trace export stays disabled by default. Set
`MANAGEMENT_TRACING_EXPORT_OTLP_ENABLED=true` and
`MANAGEMENT_OPENTELEMETRY_TRACING_EXPORT_OTLP_ENDPOINT` to a reachable `/v1/traces`
destination when running outside Compose. Do not use `localhost` inside containers.
OTLP metrics and logs stay disabled; Prometheus and the file log pipeline remain.

## Privacy boundary

`TracingConfiguration` wraps each SDK `SpanExporter` in `SafeSpanExporter` before
the SDK consumes it. This final boundary preserves IDs, parenting, timing, names,
resources and status code; it removes status descriptions, span events (including
exception messages/stacks), links and non-allowlisted span attributes.
The allowlist is bounded HTTP method/status/template/outcome, exception type and
configured client name. Attribute values have a 256-character conservative character
limit, with original scalar types retained. Exception type remains useful without
unbounded exception messages. Framework names use HTTP methods/route templates.

Full URLs, queries, raw paths, Authorization, JWTs, passwords, cookies, bodies,
usernames/emails and request/correlation IDs are not permitted attributes. Client
URL attributes are deliberately removed rather than attempting incomplete URL
redaction. Client spans may have less destination detail than a default OTel span;
`client.name` remains and the server span supplies the matched route template.
Do not add manual sensitive span names/resources or high-cardinality conventions.
No HTTP header/body capture is enabled. Tests exercise sentinel credentials and
query strings against actual HTTP instrumentation and exported span data.

## Collector and Tempo

Collector Contrib **0.143.0**, pinned image, HTTP receiver only, memory limiter first
(192 MiB limit / 48 MiB spike / 1s check), batch (256 desired / 512 maximum / 1s),
two export workers and a persistent byte-sized queue (64 MiB by default), with
exponential retry 1–10s and no elapsed-time expiry. Phase 4 uses the supported
`file_storage/queue` extension, fsync, startup/rebound compaction (32/8 MiB), and
the `otel_queue` volume mounted at `/var/lib/otelcol`, owned by UID 10001.
`OTEL_QUEUE_CAPACITY_BYTES` controls admission capacity; overflow rejects new
exports rather than blocking indefinitely. Physical database size can exceed
payload capacity and compaction needs spare disk space.
Container: non-root 10001, read-only root, 256 MiB, 0.5 CPU,
64 PIDs, GOMEMLIMIT 180 MiB, unless-stopped, 30s stop grace. Health extension
listens internally on 13133. No diagnostics/debug/metrics endpoint is published;
no metrics/logs pipeline is configured. The queue survived a controlled Collector
restart while Tempo was unavailable; all three test traces arrived after recovery.
This is not exactly-once delivery or a crash-durability guarantee. App exporter
buffers, the Collector batch processor and pre-admission data remain volatile;
overflow, disk exhaustion or process crashes can still lose traces. See
[Phase 4 verification](phase4-verification.md) for the tested scope.

Tempo **2.9.0**, single binary, OTLP gRPC on internal 4317 and HTTP query/readiness
on internal 3200. Non-root 10001, read-only root, 512 MiB / one CPU / 128 PIDs,
45s stop grace, unless-stopped. A network-disabled one-shot storage initializer
sets ownership of the new volume root only. `springboot_project_tempo_data`
persists `/var/tempo/wal` and `/var/tempo/blocks`. Configured block retention is
**72 hours**, with 5-minute maximum ingester block duration. Retention is a
policy, not a hard disk quota; deletion enforcement is not verified by this phase.
No metrics generator, service-graph or remote-write pipeline is enabled.

The pinned images are shell-less. Native health/readiness endpoints are checked
from the existing trusted Prometheus container, rather than installing tools in
them or publishing diagnostic ports:

```powershell
docker compose -p springboot_project exec -T prometheus wget -q -O - http://otel-collector:13133/
docker compose -p springboot_project exec -T prometheus wget -q -O - http://tempo:3200/ready
```

These containers have no Docker HEALTHCHECK; an orchestrator should probe these
endpoints internally. Health-extension availability does not itself prove export;
the verifier queries real stored spans separately. The trust boundary is the
existing `springboot_project_default` bridge and privileged Docker administrators.
Ingestion/query endpoints are unauthenticated plaintext within that boundary.
Do not attach untrusted workloads. TLS/authentication, HA, remote object storage,
backups, crash recovery and hard disk quotas still need Phase 6 review. Phase 4
adds a persistent queue without changing the internal transport trust boundary.

## Grafana navigation

Provisioned UID `tempo`, URL `http://tempo:3200`, proxy mode, non-default/non-editable.
Loki stays default; Prometheus and existing data are preserved. Loki's derived
TraceID field matches the actual JSON `"traceId":"<32 lowercase hex>"` and opens
Tempo. Provisioning escapes Grafana's value macro as `$${__value.raw}`.
Tempo trace-to-logs uses Loki UID `loki`, maps resource `service.name` to existing
`service` label, filters by trace ID and searches one minute either side of a span.
No trace ID becomes a Loki label. Navigation needs an ingested log and a stored
sampled trace within retention; absent data yields no result.

Grafana Explore -> Tempo -> TraceQL examples:

```traceql
{ resource.service.name = "learning-api" }
{ resource.service.name = "user-learning" && span:kind = server }
{ resource.service.name = "jwks-service" && duration > 100ms }
{ status = error }
```

Paste an observed trace ID in Explore's Trace ID query to inspect the waterfall.
Do not substitute independent endpoint traces for a verified Learning -> User chain.
Full operations dashboards/alerts remain Phase 5.

## Verification

From each independent module: `.\mvnw.cmd -o test` (use online mode once if
managed dependencies are not cached). New tests use real servlet/client HTTP,
W3C and tracestate, malformed parents, sampling=0/1, async context, parenting,
correlation, counts and privacy; previous JWT/JWKS/logging/metrics suites remain.

```powershell
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml config --quiet
python observability/verify-baseline.py --runtime
python observability/verify-tracing.py --snapshot
# Build/recreate only affected services, as recorded in phase3-verification.md.
python observability/verify-tracing.py --restart-tempo
python observability/verify-metrics.py --credentials observability/local-test-credentials.json
```

Take `--snapshot` **before** deployment; it stores only public response fingerprints,
container topology/identity and protected file hashes in an ignored local file.
Do not overwrite it before comparing preservation. Optional existing ignored test
credentials support login, internal JWT and logout; the verifier creates no accounts
and logs out its own refresh session. Without them those checks are NOT VERIFIED.
`--restart-tempo` is an explicit ordinary controlled restart and compares trace
availability afterward. It does not prove crash durability or retention deletion.

References: [Boot tracing and managed HTTP clients](https://docs.spring.io/spring-boot/reference/actuator/tracing.html),
[Collector configuration](https://opentelemetry.io/docs/collector/configuration/),
[pinned Collector manifest](https://github.com/open-telemetry/opentelemetry-collector-releases/blob/v0.143.0/distributions/otelcol-contrib/manifest.yaml),
[Tempo configuration](https://grafana.com/docs/tempo/latest/configuration/).
