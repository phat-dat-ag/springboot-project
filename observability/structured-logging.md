# Phase 1 structured logging contract

This is the current logging contract for the three independently built services.
Identity/configuration standards remain in [README.md](README.md). Test and rollout
evidence is recorded separately in [phase1-verification.md](phase1-verification.md).
No OTel logging, new backend, tracing bridge, metrics deployment or retention change
is part of Phase 1.

## JSON fields

| Field | Type | Meaning |
| --- | --- | --- |
| `@timestamp` | String | UTC ISO timestamp with milliseconds, e.g. `2026-11-10T08:00:00.123Z` |
| `level`, `logger_name`, `thread_name`, `message` | String | Standard encoder fields; never duplicated by MDC |
| `service` | String | `user-learning`, `learning-api`, `jwks-service`; existing Loki labels preserved |
| `serviceVersion`, `environment` | String | Existing Phase 0 release/deployment metadata |
| `event` | String | `http.request.started`, `http.request.completed`, or named business/lifecycle event |
| `correlationId` | String | Effective validated request ID; numeric-looking IDs remain strings |
| `traceId`, `spanId` | String, optional | Existing framework-owned context only |
| `http.request.method` | String | HTTP method from a bounded set; otherwise `OTHER` |
| `http.route` | String | Matched route template; otherwise `UNMATCHED` |
| `http.response.status_code` | Integer | Final observed HTTP status |
| `durationMs` | Number | Monotonic elapsed milliseconds, nonnegative |
| `outcome` | String | `success` (1xx-3xx), `client_error` (4xx), `server_error` (5xx), `unknown` otherwise |
| `error.category` | String | `none`, `authentication` (401), `authorization` (403), `client`, or `server` |
| `error.type` | String, optional | Exception class, without its message |
| `errorCode` | String, optional | Bounded internal enum-style code |
| `asyncTimedOut` | Boolean | Async listener observed a timeout |
| `stack_trace` | String, optional | Exception types/frames with messages omitted and diagnostic volume bounded |

Optional approved diagnostics: validated `callerService`, `callerInstance`,
`callerVersion`, `callerIdentitySource=self-reported`, direct `peerAddress`,
`protocol`, and separately named validated `callerTraceId`/`callerSpanId`. The latter
describe an incoming W3C parent, not SDK-created server spans. `User-Agent`, cookies,
Authorization, raw paths, query strings, request/response bodies and arbitrary MDC
or structured key-value fields are excluded.

`key_count`, `startup_ms`, `stage`, `key_index`, `resultCount`, `upstream.status`
and `upstream.errorType` support bounded operational diagnostics. Numeric values are
written as SLF4J key-value numbers, not strings in MDC. Default encoder timestamp,
level and thread/logger fields remain the encoder's responsibility.

Metadata is set through typed Logback encoder properties. Values outside the
Phase 0 bounded character policy become `unknown`, never interpolated as raw JSON.
This also removes the risk of a malformed multiline `customFields` object.

Example sanitized completion (additional standard encoder fields omitted):

```json
{
  "@timestamp": "2026-11-10T08:00:00.123Z",
  "level": "INFO",
  "message": "API request completed",
  "service": "learning-api",
  "serviceVersion": "0.0.1-SNAPSHOT",
  "environment": "development",
  "correlationId": "example-request-1",
  "event": "http.request.completed",
  "http.request.method": "GET",
  "http.route": "/api/v1/learning/internal-test/users/{id}",
  "http.response.status_code": 200,
  "durationMs": 12,
  "outcome": "success",
  "error.category": "none",
  "asyncTimedOut": false
}
```

## Lifecycle and correlation

`logging/filter/RequestLoggingFilter` runs after the framework observation scope
but before Spring Security. Explicit registration includes REQUEST, ASYNC and ERROR
dispatches. The previous User/Learning correlation and completion filters are removed
so there is one owner.

- Accept exactly one `X-Correlation-ID` matching
  `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`. Missing, blank, duplicate, oversized or unsafe
  values are replaced with a UUID; the business request is not rejected for a bad ID.
- Return the effective ID, including security/error responses where headers can
  still be written. Never log the rejected header value.
- Scope MDC per dispatch, discard stale request-owned values, and restore the
  outer non-request context, including framework trace metadata.
- Propagate the same ID through Learning's User/JWKS clients and both User JWKS
  decoders. Existing managed builders and trace-header behavior are retained.
- Capture Spring MVC Callable diagnostic context on the worker and restore it
  afterward. Async listeners restore context for the final completion event and
  restore the callback thread's prior context afterward.
- Do not fabricate trace/span IDs. Arbitrary application-scheduled background tasks
  and SDK span propagation still require explicit task/context handling in Phase 3.

One DEBUG start event is emitted. A normal synchronous request completes after the
chain returns. Escaped exceptions and `sendError` defer completion to the container's
ERROR dispatch or request-destruction fallback, so final statuses are not guessed
prematurely. AsyncListener owns async completion. An atomic guard prevents duplicate
events across dispatches/listeners. The original route template survives `/error`.

The response status is authoritative. Only at final completion, if an unhandled
failure/timeout has no error status and the response is uncommitted, use 500 as a
fallback. No response body, auth decision or status is changed by the logging code.

## Severity and exception ownership

| Situation | Policy |
| --- | --- |
| Request start | DEBUG |
| Successful ordinary request | INFO completion |
| Successful Actuator health request | DEBUG completion; no routine INFO noise |
| HTTP 4xx, including 401/403 | WARN completion |
| HTTP 5xx | ERROR completion |
| Important auth/business/lifecycle success | INFO named event, no account/session/token values |
| Lookup details, expected rejection reasons and controller delegation | DEBUG |
| Upstream User request failure | WARN with safe status/type; no upstream body or exception dump |

Global exception handlers hand safe error context to the request completion owner;
they do not emit the same exception stack again. Their API response contracts stay
unchanged. Standalone/non-request fallback diagnostics still use safe rendering.

All exception messages (including causes/suppressed exceptions) are omitted from
stack output. Untrusted throwable-bearing messages and known unsafe framework
diagnostic messages are generalized. Types, frames and approved error fields remain.
Stacks are bounded by cause depth, count, frame count and approximately 8 KiB of
text; truncation may omit deep diagnostic frames. Missing-route warnings that echo
raw paths are suppressed. SQL/protocol/startup-analysis messages that can embed
rejected secrets are generalized, not copied verbatim.

## Sensitive-data policy

User authentication/registration logs no longer include username, email, password,
user ID, refresh-session ID, raw token or token hash. Search filters are not logged.
Successful auth operations retain named events and correlation context. Logging
an entire DTO, environment map, token object or arbitrary exception message remains
prohibited; JSON escaping and hashing are not redaction.

The MDC and SLF4J key-value allowlists are a final boundary, not permission to put
secrets in `message`. New business messages must use constant text and approved,
non-sensitive structured values. Do not enable SQL/body/wire debug logging in a
production environment without a separate privacy review.

## Collector and historical compatibility

The existing file -> Fluent Bit -> Loki/OpenSearch route, service labels and index
names remain. The collector's read-only custom parser uses `@timestamp` as event
time and keeps it in JSON; numeric JSON fields remain numeric. The `%L` fractional
second parser supports old nanoseconds and new milliseconds; see the
[Fluent Bit 3.2 parser documentation](https://docs.fluentbit.io/manual/3.2/pipeline/parsers/configuring-parser).
Unparsed records lack a canonical service and are dropped by the grep allowlist.
They are not forwarded as raw `log` strings; drop counters/alerting are future work.
Existing long-line skipping remains configured.

Historical `httpMethod`, `uri`, `status`, `elapsed_ms` records remain searchable.
Phase 1 emits only the new HTTP fields; it does not emit conflicting aliases.
OpenSearch's historical `status`/`elapsed_ms` text mappings are not modified.
New canonical HTTP status/duration names receive numeric mappings on ingestion.
No index is deleted, recreated or reindexed. If canonical names already have
incompatible mappings in another deployment, stop and approve a versioned index
migration in Phase 4 rather than attempting an in-place type change.

Existing Grafana queries use service/level and remain valid. The OpenSearch setup
script refreshes field metadata and upgrades only its exact original default
Discover columns; personal customizations are preserved. Historical values remain
in expanded documents and legacy-field queries. No new Grafana dashboard is added.

Successful readiness requests intentionally do not generate INFO log records now.
For a public ingestion probe, request JWKS `/api/v1/jwks/user` with a chosen valid
correlation ID, then search that ID. Use authenticated API calls to verify all three
services and Learning -> User propagation. Full tracing/exporters remain deferred.
