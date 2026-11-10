# Phase 1 implementation and deployed-runtime verification

Date: 2026-11-10. Runtime checks approximately 03:00–03:12 UTC (10:00–10:12 Bangkok).
This report supplements the [logging contract](structured-logging.md),
[baseline](README.md), and [phase gates](phase-plan.md).

## A. Executive summary

Phase 1 logging implementation is tested and deployed to `springboot_project`.
All **282 Maven tests passed, zero failures/errors/skips**. Fresh application JSON,
Learning -> User correlation, authenticated internal JWT calls, public JWKS,
login/logout, 401/404/500 completions, and both logging backends were verified.
Runtime non-admin 403 rejection remains **NOT VERIFIED** because the supplied
account has admin access; real embedded-container tests cover 403 completion.
No account/role was changed to force this check.

The existing file -> Fluent Bit -> Loki and OpenSearch architecture remains.
No dependency upgrade, OTel logging, metrics/tracing deployment, new dashboard,
retention overhaul, Git commit/push, or branch operation was performed.

## B. Changes by repository

The root and all three submodule working trees were clean before implementation.
Every change listed here belongs to Phase 1. The final Git inventory is below.

### Root

- `docker-compose.yml`: one read-only custom Fluent Bit parser bind mount.
- `observability/fluent-bit/fluent-bit.conf`, new `parsers.conf`: application UTC
  timestamp parsing; canonical-service allowlist drops unparsed fallback records.
  Existing inputs/checkpoints, labels, destinations and index names remain.
- `observability/opensearch/setup-dashboards.ps1`: refresh field metadata; migrate
  only the exact original default Discover columns. Preserve custom views/history.
- `observability/verify-baseline.py`: explicitly permit only the new parser mount
  while continuing to enforce existing ports/storage/networks/configuration.
- New `observability/verify-structured-logging.py`: repeatable local runtime probes;
  optional credentials come from `OBS_TEST_USERNAME` / `OBS_TEST_PASSWORD` process
  environment, never a committed credential or printed response. It logs out the
  refresh session it creates, including when an authenticated assertion fails.
- `observability/README.md`, `grafana/README.md`, `opensearch/README.md`, new
  `structured-logging.md` and this report: current schema, policies and evidence.

### Shared pattern in the three independent modules

Each module owns its implementation under its existing `logging` package; no
shared-library/module architecture was introduced:

- `filter/RequestLoggingFilter.java`: one correlation/lifecycle owner, safe route,
  final numeric status/duration, ERROR/ASYNC dispatch and MDC scope handling.
- `RequestLoggingConfiguration.java`: explicit servlet dispatcher/async registration
  and request-destruction fallback listener.
- `StructuredJsonEncoder.java`, `SafeMessageJsonProvider.java`,
  `SafeThrowableConverter.java`: identical field/metadata/exception safety policies.
- `src/main/resources/logback-spring.xml`: shared encoder policy for file/console,
  safe typed metadata setters; existing file paths/rotation unchanged.
- Focused encoder, filter and embedded-Tomcat/security tests.

### User

- Removed superseded `common/filter/CorrelationIdFilter.java` and
  `logging/ApiLoggingFilter.java`; updated imports/tests.
- `common/exception/GlobalExceptionHandler.java`: passes handled exception/category
  context to completion logging instead of duplicating stacks.
- `controller/AuthController.java`, `UserManagementController.java`,
  `service/impl/AuthServiceImpl.java`, `RefreshTokenServiceImpl.java`,
  `UserManagementServiceImpl.java`: remove identifying/token/hash/search values;
  named safe auth successes; routine details at DEBUG.
- `security/jwks/CallerMetadataInterceptor.java`: bounded outgoing metadata/ID.
- `security/jwt/user/JwtDecoderConfig.java`,
  `security/jwt/internal/InternalJwtDecoderConfig.java`: managed caller interceptor
  on both JWKS clients; authentication validators/contracts unchanged.
- `application.properties`: disable plaintext startup banner.
- New `logging/BusinessLoggingPrivacyTest.java`; existing decoder tests updated.

### Learning

- Removed the same two superseded filters; safe completion exception ownership.
- `client/UserServiceClient.java`: safe upstream status/type diagnostics without
  response bodies or user identifiers; original error translation unchanged.
- `controller/JwksIntegrationController.java`: routine fetch detail at DEBUG.
- `security/jwks/CallerMetadataInterceptor.java`: bounded outgoing metadata/ID.
- `application.properties`: disable plaintext startup banner.
- `client/UserServiceClientTest.java`: actual incoming filter -> local HTTP stub
  propagation assertion, response ID and cleanup.

### JWKS

- Replaced existing request filter internals with the same lifecycle standard;
  retained its sound validation and safe caller-diagnostic ideas.
- `security/RsaKeyProvider.java`: logging-only duration field standardization.
- Updated `LoggingConfigurationTest.java`; expanded filter/encoder/servlet tests.
- No controller, public key, JWT contract, issuer/audience, endpoint or security
  decision was changed.

## C–F. Logging, correlation, errors and privacy

The exact schema and policies are in [structured-logging.md](structured-logging.md).
Canonical `service` values remain `user-learning`, `learning-api`, `jwks-service`;
`serviceVersion=0.0.1-SNAPSHOT`, `environment=development` were observed live.

Completion fields include string `correlationId`, `http.request.method`,
`http.route`, numeric `http.response.status_code` and `durationMs`, string
`outcome`/`error.category`, optional safe `error.type`/`errorCode`, boolean
`asyncTimedOut`. Encoder timestamp/level/logger/thread/message fields are not
duplicated. Existing framework trace/span MDC is preserved; no IDs are fabricated.

Correlation accepts exactly one 1–64 character ID matching
`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`; invalid/missing/duplicate input becomes a UUID.
Effective IDs are returned, propagated through internal clients and scoped to
dispatch/async completion; reused threads do not retain request-owned MDC.

Request starts are DEBUG; normal completions INFO; successful health completions
DEBUG; 4xx WARN; 5xx ERROR. Escaped/sendError/async paths log once at final
completion, retaining the original matched template rather than `/error`.
Unknown routes are `UNMATCHED`, never the raw requested path/query.

Removed exposure risks included usernames/emails, user/session IDs, search input,
refresh-token hashes and upstream response bodies in application logs. Encoder
MDC/KV allowlists reject arbitrary secrets; throwable messages (including nested
causes/suppressed messages) are omitted, frames/types retained with size bounds.
Known unsafe framework diagnostics are generalized. Authorization, cookies,
bodies, raw paths and query strings are never collected by the request logger.
This is not permission to log secrets in new free-text business messages.

## G. Automated validation

Commands were actually run from each module directory:

```powershell
.\mvnw.cmd -o test
```

| Module | Tests | Failures | Errors | Skips | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| User | 96 | 0 | 0 | 0 | PASS |
| Learning | 111 | 0 | 0 | 0 | PASS |
| JWKS | 75 | 0 | 0 | 0 | PASS |

The new filter contract has 29 invocations per module; encoder contracts have two
per module. Real embedded Tomcat tests cover successful/template-safe requests,
anonymous 401, authenticated role-based 403, escaped 500 and MVC Callable
completion with exactly one final event. Unit tests additionally cover malformed,
oversized/duplicate IDs, stale MDC/thread reuse, final async/error/timeout statuses,
numeric types, sensitive inputs and trace-context preservation. Existing auth,
internal JWT, key-loading and endpoint regression tests remain enabled.

Focused reruns also executed:
`.\mvnw.cmd -o test "-Dtest=StructuredJsonEncoderTest"` in each module.

Failures found and fixed before the final full runs:

- Existing committed Learning file-appender `customFields` JSON lacked a comma;
  typed encoder metadata eliminates this fragile raw JSON configuration.
- Embedded-test Logback file handles prevented Windows temporary-file cleanup;
  test context shutdown now closes the logging context.
- Synthetic encoder test events needed explicit timestamp/thread/MDC initialization.

No assertions were weakened to conceal application failures. Last source-only
cleanup removed trailing whitespace after the final suites; no behavior changed.

## H. Deployment commands and runtime evidence

All Compose mutations explicitly targeted `springboot_project`, preserving the
existing `.env`, base/debug overrides and JDWP bindings. Commands actually run:

```powershell
docker compose -p springboot_project --env-file .env -f docker-compose.yml config --quiet
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml config --quiet
python observability/verify-baseline.py
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml build user-api learning-api jwks-api
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build --wait --wait-timeout 120 jwks-api
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build --wait --wait-timeout 120 user-api learning-api
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build --wait --wait-timeout 60 fluent-bit
docker compose -p springboot_project exec -T fluent-bit /fluent-bit/bin/fluent-bit --dry-run -c /fluent-bit/etc/fluent-bit.conf
python observability/verify-structured-logging.py
powershell -NoProfile -ExecutionPolicy Bypass -File observability/opensearch/setup-dashboards.ps1 -DashboardsUrl http://localhost:5677
python observability/verify-baseline.py --runtime
```

All commands above passed in their final execution. Image builds use existing
Dockerfiles with `-DskipTests`; the full suites were run separately first. Maven
reported nonfatal unavailable Apache snapshot-prefix metadata during image builds;
all images built successfully. No dependency/configuration workaround was added.

The initial direct `.ps1` execution was blocked by Windows execution policy. The
process-only bypass above succeeded without changing machine policy. Discover
metadata refreshed to 81 fields; only untouched default columns migrated.

Additional executed read-only/probe command families:

- `git status --short`, `git diff --check`, branch/HEAD inspection in root and all
  three modules; source/config reads using `rg`, `Get-Content`, `git show/diff`.
- `docker ps -aq`, `docker inspect <captured IDs>`; Python normalized before/after
  snapshots and SHA-256 comparisons without printing secret/key contents.
- `docker compose -p springboot_project logs --no-color --no-log-prefix
  [--since <probe start>] <service>` captured/parsed in memory, never printed raw.
- Python HTTP GET/POST probes in the reusable verifier; credentials/token bodies
  supplied only in process memory. The successful run marker was
  `phase1-7df21d4e09b3463f`.
- Local `postman request GET http://localhost:8783/api/v1/jwks/user
  --no-report-events --response-only --timeout 20000 --script-post-request
  <three pm.test assertions>`: exit 0; HTTP 200, public RSA-only response and
  correlation-header format. Response/key body captured and withheld.
- Loki `/loki/api/v1/query_range`; OpenSearch `/springboot-*-logs/_search`,
  `/_mapping`, `/_cat/indices`, `/_cluster/health`; Grafana `/api/health`.
  These were read-only in-memory HTTP queries.

### Changed containers and preservation

Exactly four container identities changed:
`springboot_project-{jwks-api,user-api,learning-api,fluent-bit}-1`.
The APIs are **healthy**; Fluent Bit is **running** (no configured healthcheck).
Its image is unchanged. The new read-only parser mount is the only added mount.

Before/after comparison verified **25 unrelated containers unchanged**, including
all **16 `jp_dev` containers**: identity, image, start time, restart count, ports,
mounts and network membership. All 10 protected real environment/key fingerprints
matched. Existing named volumes, databases, checkpoints, network memberships,
HTTP/debug ports, and original mounts were preserved. No `down`, forced recreation,
volume deletion, index deletion/reindex, key rotation or migration runner was used.

### Live checks

| Check actually observed | Result |
| --- | --- |
| All three readiness endpoints | 200 / PASS |
| Valid/malformed/oversized correlation ID response behavior | PASS |
| Missing and duplicate correlation headers on all three deployed services | PASS; generated/replaced UUID and preserved original HTTP status |
| Login, Learning identity, logout of verification refresh session | 200 / PASS |
| Learning -> User internal JWT authenticated user lookup | 200 / PASS |
| Anonymous User internal / Learning protected routes | 401 / PASS |
| Malformed JWT; user JWT incorrectly used as internal JWT | 401 / PASS |
| Unknown JWKS route | 404 / PASS |
| Missing User via Learning | User 404 -> existing Learning 500 / PASS |
| Invalid refresh sentinel | 404 / PASS; no token/hash in captured logs |
| Exactly one final completion with numeric status/duration for the checked requests | PASS |
| No tested credentials/token/body/header/query/path sentinels in captured logs | PASS |
| Health-check INFO suppression | PASS |
| Real non-admin 403 request | NOT VERIFIED; no suitable account supplied |
| 403, async/error lifecycle, MDC/thread reuse | PASS in automated tests; not all fault-injected into deployed APIs |

The first exploratory runtime run expected `/admin/users` to reject the supplied
account, but it returned 200 because the account is an admin. Its refresh session
was logged out in `finally`. A JWKS POST returned 401 rather than the exploratory
403 expectation; a CORS preflight returned 200. Those probes were not counted as
403 verification. The final verifier explicitly reports this limitation. One
diagnostic import used an incorrect module name; it made no application change.

### Backends and timestamps

Fresh completion records from all three services appeared in **both Loki and
OpenSearch**. Exact correlation `phase1-7df21d4e09b3463f-linked` appeared once for
Learning and once for User in each backend, both 200, with templates
`/api/v1/learning/internal-test/users/{id}` and `/internal/users/{id}`.
Loki event timestamps matched JSON application timestamps within 2 ms.

All three indexes now map canonical status and `durationMs` as `long`; existing
legacy `status`/`elapsed_ms` remain `text`. Existing indexes/history were preserved;
the final baseline sample counted about 71k documents per service. No unsafe
in-place mapping rewrite or alias duplication was attempted.

A post-start sample parsed 46 User, 39 Learning and 46 JWKS application JSON
records with correct identity/version/environment and zero OTLP exporter warnings
or errors. Fluent Bit had zero error/flush-failure lines in its checked startup
window. Native parser/config dry-run passed. This proves the observed window,
not indefinite reliability or outage recovery.

Grafana health was `ok`. OpenSearch remained **yellow**, as in Phase 0's existing
single-node deployment; no cluster/replica/retention changes were made. Successful
health requests now produce no INFO records, so quiet API indexes are expected
when only readiness probes run; use a public JWKS or authenticated API ingestion
probe rather than interpreting silence as a collector failure.

## I. Cross-project JWKS compatibility

`japanese-learning` requires **no changes**. Read-only review of its .NET JWKS
retriever and Quarkus configuration confirmed the same public endpoint contract.
User/Learning JWKS bodies, RSA key material/key IDs, content types and
`Cache-Control: max-age=300, public` matched the pre-deployment snapshot exactly.
Consumer JWT validation, issuer/audience, paths/security/network contracts did not
change; only safe diagnostic header handling/logging did. All its `jp_dev`
containers remained unchanged. Its pre-existing `angular`/`quarkus` Git changes
were not touched; its JWKS submodule was clean.

## J. Limits and future phases

- Non-admin deployed 403 needs an existing suitable account; embedded real-security
  test coverage is present. No real account was created or modified.
- Production async/timeout fault injection and malformed collector-record injection
  were not performed; automated lifecycle tests and native config validation pass.
- Arbitrary application-scheduled background tasks need explicit context handling;
  MVC Callable and async final completion scopes are covered.
- User real trace/span context is preserved, but complete cross-service distributed
  traces are not implemented (Phase 3). No active exporter/destination was added.
- Drop counters/alerts, outage durability, bounded Docker logging, backend access
  controls, retention/rollover and historical-schema migrations remain later work.
- Plain free-text messages still require safe development practices; the encoder
  cannot infer every possible secret in every future business message.
- Authenticated Grafana UI navigation, indefinite ingestion availability and
  retention deletion were not verified. No new dashboards were deployed.

## K. Acceptance criteria

| Phase 1 criterion | Status | Evidence |
| --- | --- | --- |
| Inspect/preserve existing pipeline and Phase 0 identity | PASS | Source review, baseline/runtime verifier, unchanged destinations/labels |
| Consistent JSON schema/types and optional real tracing MDC | PASS | Encoder tests; fresh logs/backend numeric mappings |
| Validated/returned/propagated correlation ID and MDC cleanup | PASS | 29 filter cases/module, client test, live linked call |
| Final HTTP success/4xx/5xx lifecycle including security/async/errors | PASS | Unit and embedded-container tests; live 200/401/404/500 |
| Deployed non-admin 403 behavior/logging | NOT VERIFIED | Supplied account is admin; no roles modified |
| Safe business severity and sensitive-data regression protection | PASS | Source changes, privacy/encoder tests, live sentinel scan |
| Collector JSON/timestamp parsing and both destinations | PASS | Native dry-run, timestamp assertions, fresh ingestion all three services |
| Safe downstream historical field migration | PASS | New numeric mappings, legacy/history retained, default Discover refresh |
| All three relevant Maven suites | PASS | 282 tests, zero failures/errors/skips |
| Safe deployment and preservation | PASS | Four intended recreations; 25 unrelated/16 jp_dev unchanged; 10 fingerprints |
| Existing auth/JWKS/internal JWT compatibility | PASS | Existing tests plus live login/logout/key equality/internal call |
| Unexpected OTLP errors absent in checked window | PASS | Post-start log scan; no exporter activation |
| Documentation and phase boundaries | PASS | This report and schema; no Phase 2–6 implementation |
| No commit/push/reset/branch change or unrelated repository modifications | PASS | Before/after Git inspection |

Implementation and deployment are ready for review. The explicit runtime gap above
must not be presented as verified. No Phase 2 work is authorized by this report.

## L. Git state

Root and all three independent module repositories remain on `develop`, with
unchanged HEADs. Changes are unstaged; nothing was committed or pushed. Root has
the observability/Compose edits and three dirty submodule pointers. User/Learning
have the two obsolete filters deleted and their new logging/test files untracked;
JWKS has existing logging files modified plus new configuration/provider/tests.
No pre-existing edits in these four repositories were reset or overwritten (all
four were clean initially). Real `.env` and key files are unchanged.

Use `git status --short` in root and each module for the exact current inventory;
the changes-by-repository section above lists the implementation scope. Initial
temporary editing helpers, Python bytecode and the temporary deployment snapshot
were removed after verification; no credentials file was created.
