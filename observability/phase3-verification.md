# Phase 3 implementation and deployed verification

Date: 2026-11-11. Evidence is from this checkout and the existing
`springboot_project` deployment. [Tracing operations](tracing.md) describes the
configuration; this record distinguishes observed results from acceptance gaps.

## A. Executive summary

**Implemented, tested and deployed; all critical Phase 3 acceptance criteria now PASS.**
The authenticated follow-up in section O validated the existing ignored credentials
file and verified deployed login, refresh, logout and Learning -> User internal-JWT
tracing. Actual Tempo spans and both logging backends confirmed the parent chain
and independent correlation. No application defect or code change was required.
Earlier missing-credentials attempts are recorded as history in section O; they
are superseded by the successful runtime evidence, not by automated substitutes.

All **300 Maven tests passed**, zero failures/errors/skips in the final suites.
Collector, Tempo and all three APIs are running. Real spans reached Tempo from all
three services, and a real Learning -> JWKS three-span chain was verified. The
pre-restart traces remained queryable after one ordinary controlled Tempo restart.
Existing logging/metrics/JWKS compatibility and preservation checks passed.
No commits, pushes, branch changes, resets or Phase 4Ã¢â‚¬â€œ6 implementation were made.

## B. Changes by service

| Area | Changes |
| --- | --- |
| User | Retain existing Boot OTel starter; root sampling default 1.0 -> 0.1; explicit W3C/parent-based sampler, async context propagation, omit only nested security spans; privacy-wrapped exporter; three new tracing/privacy test invocations; update baseline default assertion and env example |
| Learning | Add Boot-managed OTel starter; same tracing/privacy configuration and tests; use existing production ServiceClientConfig in a two-context real-HTTP tracing fixture; no production HTTP/JWT client refactor |
| JWKS | Add Boot-managed OTel starter; same tracing/privacy configuration and tests; restclient starter in test scope only; no controller, key, API, auth or network contract change |
| Root | Pinned Collector/Tempo configuration and services, new Tempo volume initializer, trace export environment for APIs, Tempo datasource, Loki derived field and trace-to-logs settings, updated examples/docs/baseline verifier, reusable secret-safe runtime verifier |

Existing Java files were not reformatted. New Java files follow the supplied rules.
The one existing baseline assertion changes because the intended sampling default
changes; no test was disabled or weakened to hide a failure.

## C. Architecture and resolved versions

Spring servlet/client observations -> Micrometer OTel bridge -> OTel SDK -> OTLP
HTTP/protobuf Collector -> OTLP gRPC Tempo -> Grafana. No agent, second bridge,
manual production HTTP span, metrics generator pipeline, OTLP metric/log exporter,
or replacement for Logback/Fluent Bit/Loki/OpenSearch/Prometheus was introduced.

| Service | Boot | Micrometer Tracing / OTel bridge | OTel SDK trace |
| --- | --- | --- | --- |
| User (`user-learning`) | 4.1.1 | 1.7.1 | 1.62.0 |
| Learning (`learning-api`) | 4.1.2 | 1.7.2 | 1.62.0 |
| JWKS (`jwks-service`) | 4.1.2 | 1.7.2 | 1.62.0 |

Versions were read from actual POMs and resolved final Surefire classpaths. All
modules still target Java 17; local Maven used installed Java 17.0.19. Existing
User/Learning Docker JDK 21 and JWKS JDK 17 were preserved. No Java/Boot upgrade.
Resources preserve canonical names, Maven/app version and deployment environment.

## D. Propagation and correlation

W3C `traceparent`/`tracestate` extraction/injection is SDK-owned. Real HTTP tests
continue a valid parent, reject all-zero trace IDs, generate fresh valid trace/span
IDs, carry tracestate, and assert exactly two SERVER and one CLIENT span with a
correct chain and distinct span IDs. Learning additionally uses a second servlet
context identified as `user-learning` and its actual production managed User client.
The fixture intentionally isolates tracing; existing JWT suites independently
test production token behavior; the deployed authenticated chain also passed in section O.

Correlation validation/response header/client propagation, MDC cleanup, security
and one final completion remain owned by Phase 1. Existing encoder fields are
reused, without a second MDC provider. MVC Callable tests continue tracing and
correlation and finish with one server span. Existing error/async/completion
regressions remain passing. Live marker completions occurred exactly once per
service in both backends, with matching trace IDs and valid own span IDs.

## E. Sampling and security

Uniform default 0.1 root probability; Compose root variable
`TRACING_SAMPLING_PROBABILITY` maps to all API probabilities. Explicit OTel
`parent-based-trace-id-ratio` honors remote decisions. Tests run root probabilities
0 and 1, proving sampled remote parents continue even at zero local root probability.
Production-wide 100% was not hardcoded or deployed. Deterministic live probes used
valid sampled remote parents while the root budget remained 0.1.

SafeSpanExporter allowlists bounded HTTP method/status/template/outcome, exception
type and configured client name. Original attribute types are retained; URL/query,
arbitrary headers, credentials/PII, events, links and status descriptions are removed.
Actual exported HTTP spans and a focused exception/credential exporter test check
sensitive sentinels. Standard names/routes remain framework-owned. Baggage propagation/correlation are explicitly disabled, including W3C baggage
which Boot otherwise enables with an empty remote-fields list. Real-HTTP tests
assert that incoming baggage, Authorization and Cookie are not copied to the
downstream fixture. No capture of
raw bodies, tokens, passwords, cookies, keys, username/email or arbitrary baggage
is enabled. No telemetry ID is added as a metric or Loki label.

Logs can contain trace IDs when their traces are unsampled, lost or expired;
log-to-trace links do not guarantee a stored trace for every request.

## F. Collector and Tempo deployment

| Component | Actual configuration / evidence |
| --- | --- |
| Collector | `otel/opentelemetry-collector-contrib:0.143.0`; native `validate` passed; HTTP receiver4318, memory limiter192 MiB/spike48, batch256/max512/1s, two workers/256-batch RAM queue, retries1Ã¢â‚¬â€œ10s/max60s; trace pipeline only |
| Collector runtime | Non-root10001/read-only root, 256 MiB/0.5 CPU/64 PIDs/GOMEMLIMIT180 MiB, unless-stopped; health extension13133 returned Server available |
| Tempo | `grafana/tempo:2.9.0`; loaded config and accepted gRPC4317; query/readiness3200; persisted WAL/blocks under new `springboot_project_tempo_data` |
| Tempo runtime | Non-root10001/read-only root, 512 MiB/one CPU/128 PIDs, unless-stopped, 45s grace; network-disabled one-shot initializer owns new volume root |
| Retention | Configured72h, max ingester block duration5m; deletion enforcement NOT VERIFIED; no disk quota/backup claim |
| Persistence | Three observed traces still queryable after one ordinary controlled restart, and queried again afterward; crash durability NOT VERIFIED |
| Isolation | No host-published ingestion, query or diagnostic port; existing trusted Compose bridge; plaintext/unauthenticated internally |

Both images are shell-less. Internal endpoint probes use existing trusted
containers, not an invented image HEALTHCHECK executable. No Docker healthcheck
is configured on Collector/Tempo; actual endpoint readiness was checked. Tempo
initially returned503 during startup and later became ready. Health does not by
itself prove trace delivery; stored traces were separately queried through Grafana.

RAM queue/batch data can be lost during shutdown, outages, overflow or retry
exhaustion. No persistent Collector queue, HA, advanced outage handling, TLS/auth,
object-store migration, alerting or retention deletion test was added prematurely.

## G. Grafana

Tempo UID `tempo` points to internal `http://tempo:3200`, non-default/non-editable.
Loki remains default; Loki/Prometheus datasource health remained successful.
Grafana's Tempo health API returned404 `plugin.notImplemented`; this is a plugin
capability limitation, not proof of a failed Tempo connection. Authenticated
Grafana datasource proxy `/ready`, TraceQL search and real trace-by-ID queries
all passed. Four documented TraceQL examples were accepted by deployed Tempo.

Grafana's loaded Loki derived field had UID `tempo`, rendered macro
`${__value.raw}`, and a regex that matched a real JSON traceId. Tempo trace-to-logs
maps service.name -> service, filters by trace and uses +/-1 minute. Live Loki
queries confirmed the matching services/trace IDs. Browser UI clicking is
**NOT VERIFIED**; backend connectivity/configuration/regex are verified.
No Phase 5 dashboard or alert was created.

## H. Automated tests and executed checks

Final full-suite command in **each** module:

```powershell
.\mvnw.cmd -o test
```

| Module | Tests | Failures | Errors | Skips |
| --- | ---: | ---: | ---: | ---: |
| User | 102 | 0 | 0 | 0 |
| Learning | 118 | 0 | 0 | 0 |
| JWKS | 80 | 0 | 0 | 0 |
| Total | **300** | **0** | **0** | **0** |

Counts were also summed directly from Surefire XML. The last source-only cleanup
wrapped three test expressions without changing their tokens; whitespace/import/
line-length checks ran afterward. No additional test run is claimed for that whitespace-only edit. Learning's full suite was
rerun successfully after strengthening the distinct-resource User fixture.
Existing JWT/JWKS, internal JWT, timeout/error handling, structured logging,
correlation/MDC, servlet async/errors and Prometheus metrics tests remain enabled.
There are nine new tracing/privacy test invocations (three per module).

Initial failures were investigated and corrected: Java generic list covariance in
the exporter wrapper; security observations added internal spans; an initial broad observation filter
was narrowed to a tracing-handler filter to preserve framework security metrics;
the filter retains the enclosing span for Boot?s tracing-aware meters and async
restoration without creating or ending that enclosing span. Intermediate fixture
failures exposed missing meter context and async restoration, and were corrected; SDK batch export
needed a longer bounded test wait; JWKS fixture needed a test-scoped managed
restclient starter. The real HTTP tests additionally assert that spring.security.http.secured.requests
metrics remain present alongside exactly three HTTP spans. No failure was converted to a skip. Native shell-less image
inspection also confirmed that `/bin/sh` is unavailable; no nonexistent shell
healthcheck was deployed. Maven's first sandboxed invocation could not open cache
lock files; elevated Maven access succeeded. Test logs include existing-style
nonfatal MeterFilter ordering / Java17 HttpClient worker cleanup warnings; zero
test failures is not a claim of zero diagnostic warnings.

Also executed: Python verifier syntax checks, all root/module `git diff --check`,
new Java line-length/import/whitespace review, base/debug Compose config validation,
baseline preservation/runtime validator and native Collector validation.
Docker image packaging uses existing `-DskipTests`; it does not replace local tests.

## I. Runtime evidence

Successful final runtime marker: **`phase3-838f2ed0310f4671`**.

| Probe | Observed trace ID | Span | Parent |
| --- | --- | --- | --- |
| User rejected anonymous internal request | `dd0a0c0cfdcf47d1bb23dacf2afb23c2` | `65ea9344fbc39e7e` | `00db50b3d757483d` |
| Learning rejected anonymous protected request | `871608cc92144ac589de6f3b2a3551df` | `2cce52dbe475ed8d` | `cdb4b0f6eb234ef0` |
| JWKS public lookup | `ffedf5928ad9408b865f24917a69d008` | `6765a969ba34ec92` | `674fadaf432d4c5b` |

**Real deployed Learning -> JWKS chain**, trace
`27fc34478b5f43d9b3e9a8f6356bc316`, correlation
`phase3-838f2ed0310f4671-jwks-linked`:

| Service / kind | Span ID | Parent ID | Name |
| --- | --- | --- | --- |
| learning-api SERVER | `8cc866c8d76ff002` | `81d42a0f4d194cbc` (probe remote parent) | http get /api/v1/integration/jwks |
| learning-api CLIENT | `0551911509572202` | `8cc866c8d76ff002` | http get |
| jwks-service SERVER | `c7935cdb51484596` | `0551911509572202` | http get /api/v1/jwks/{owner} |

Exactly three stored spans, same distributed trace ID, two distinct server IDs,
correct client parenting, unchanged application correlation and exactly one final
completion per server in Loki/OpenSearch. This demonstrates a live multi-service
chain. It does not by itself satisfy the separate Learning -> User gate; that gate
is now independently verified by the authenticated evidence in section O.

Persistence traces recorded before the controlled restart and successfully queried
after it (then queried again through Grafana):
`c50c27dc58dd41a9ab361a384d70151c`,
`0f40602c29cf4f69adc9fc7104b76292`,
`9ad97b00a90d4cb481abcbb24b37f88a`.
No claim is made about crash durability or 72h deletion.

## J. Deployment, regression and preservation

Mutation commands used explicit project/base/debug context:

```powershell
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml config --quiet
python observability/verify-tracing.py --snapshot
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml pull otel-collector tempo
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml build user-api learning-api jwks-api
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build tempo-storage-init
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build tempo otel-collector
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build --wait --wait-timeout 120 jwks-api user-api learning-api grafana
python observability/verify-tracing.py --restart-tempo
python observability/verify-tracing.py
python observability/verify-metrics.py --credentials observability/local-test-credentials.json
python observability/verify-baseline.py --runtime
```

`--restart-tempo` verified persistence but its first run subsequently failed the
preservation comparison because Docker returned mount lists in different orders.
Per-destination mount comparison proved contents unchanged; the verifier now sorts
mounts on both sides. The final run passed all available probes. The before snapshot
was never overwritten to conceal a difference. An earlier Grafana health probe
was corrected to use the plugin's supported proxy/query paths as described above.

Observed deployment and regression results:

- Recreated only existing APIs and Grafana; added Collector, Tempo, initializer
  and one new Tempo volume. Tempo also had one controlled restart.
- **26 unrelated existing containers unchanged**, including **all 16 jp_dev**
  containers: IDs/images/start times/restart counts/ports/mounts/network membership.
- **10 protected environment/key file fingerprints unchanged**. Original volumes,
  databases, RSA material, published application/debug ports and networks preserved.
- Three API readiness endpoints200; Prometheus healthy and three targets UP;
  existing PromQL/JVM/pool/histogram/security-counter and protected scrape probes passed.
  Framework spring.security.http.secured.requests metrics were also verified live
  in all three private scrape expositions after the final deployment.
- Real HTTP completion JSON from all APIs in both Loki/OpenSearch; matching
  correlation/trace metadata and no tested sensitive values. No duplicate log event
  for any checked marker. Existing logger schema and numeric field types preserved.
- No unexpected OTLP export warnings/errors in the checked deployed logs, both
  tracing verifier's recent window and the existing metrics verifier's log checks.
- Grafana/Loki/Prometheus connection checks passed. OpenSearch remains yellow,
  as in prior single-node phases, with fresh ingestion; no cluster setting changed.
- Existing Grafana volume provenance warning appeared again; volume was reused,
  not deleted/replaced. Docker json-file rotation remains later-phase work.
- Initial-rollout positive deployed auth flows were NOT VERIFIED without credentials.
  Section O now verifies login, refresh, logout and internal JWT communication live;
  anonymous/authentication rejection remains separately covered.

## K. JWKS cross-project compatibility

`japanese-learning` requires **no changes** and was not modified. The tracing-only
JWKS dependency/configuration does not change controllers, endpoints, public key
format, key IDs, issuer/validation policy, auth rules, errors or existing listeners.
Before/after public User/Learning JWKS response-body fingerprints, Content-Type
and Cache-Control matched exactly. RSA fingerprints and network membership were
unchanged, existing JWT/JWKS tests passed, and all 16 jp_dev containers were preserved.
Trace/correlation diagnostic headers retain their existing compatible behavior.
Existing optional API envelope `meta.traceId` can now be populated from SDK MDC
in Learning/JWKS responses; this field was already in their response model. Raw
public JWKS key documents remain byte-content compatible by canonical fingerprint.
No separate consumer implementation prompt is required.

## L. Outstanding issues and phase boundaries

1. The authenticated Learning -> User gate is now closed by section O. Keep the
   existing ignored credentials file private; it was neither printed nor modified.
2. Browser UI clicking is not exercised; datasource queries and link configuration
   are verified. Traces below 100% sampling are intentionally incomplete.
3. Collector RAM queue is not durable; prolonged outages/overflow/restarts can lose
   traces. Persistent queuing, load/outage tests, backpressure and recovery are Phase4/6.
4. Internal bridge trust is explicit. TLS/auth, HA/object storage, quotas/backups,
   crash recovery and retention deletion verification require later-phase review.
5. No Phase5 dashboards/alerts; no replacement of existing logs or metrics. Arbitrary
   unmanaged async/background work still needs explicit context handling.

## M. Acceptance criteria

PASS below means the stated evidence was obtained; NOT VERIFIED is an open gate,
not a passing result. No known final implementation/test FAIL remains.

| Requirement | Status | Evidence / scope |
| --- | --- | --- |
| 1. Inspect six documents, real versions/clients/security/Compose and Git | PASS | Source/runtime audit; initially clean four worktrees |
| 2. Boot-supported single tracing architecture; preserve metrics/logs | PASS | Managed starter/bridge, one Collector trace pipeline |
| 3. Instrument incoming HTTP in all services; IDs/names/durations/status | PASS | Real HTTP tests and stored spans across all services |
| 3. Supported outgoing managed clients; metadata/privacy/no duplicates | PASS | Managed client tests, live three-span Learning/JWKS chain, exporter tests |
| 4. W3C valid/missing/invalid parent and tracestate | PASS | Actual HTTP tests and live remote-parent spans |
| 4. Independent validated correlation and MDC completion behavior | PASS | Existing regressions plus live both-backend assertions |
| 5. Learning -> User server/client/server parenting and correlation in tests | PASS | Actual ServiceClientConfig, two HTTP contexts with distinct identities |
| 5. Deployed authenticated Learning -> User same trace and JWT success | PASS | Section O: real internal-JWT call, shared trace and parent chain |
| 5. Timeouts, JWT and error handling preserved | PASS | Existing client/JWT regressions and unchanged production client code |
| 6. JSON traceId/spanId/correlationId, no duplicate fields/events | PASS | Existing encoder/filter tests plus exact live completions |
| 6. Async/error/security behavior and MDC cleanup | PASS | MVC Callable tracing and previous lifecycle/security suites |
| 7. Environment sampling,0/1 controls,parent-based policy | PASS | Uniform0.1 default, property override tests, real HTTP0/1 tests |
| 8. Pinned Collector, limiter/batch/retry/queue/health/internal constraints | PASS | Native validation, deployed config/health, actual export |
| 9. Pinned Tempo, storage/retention/readiness/resources/internal access | PASS | Loaded config/readiness, new named volume, stored spans |
| 9. Ordinary restart trace persistence | PASS | Three before/after trace IDs queried again later |
| 9. Crash durability / retention deletion | NOT VERIFIED | Not tested or claimed |
| 10. Grafana datasource query, existing sources and real-field links | PASS | Proxy queries, datasource health, rendered macro/regex, live matching logs |
| 10. Browser navigation click | NOT VERIFIED | No UI browser session used |
| 11. Sensitive-data protections and low-cardinality templates | PASS | Export allowlist, privacy/HTTP tests and live sentinel absence |
| 12. JWKS cross-project compatibility | PASS | Exact response fingerprint/header/key/network preservation; consumers untouched |
| 13. Existing logging/metrics/scrape pipelines preserved | PASS | Metrics verifier, baseline and both-backend live ingestion |
| 14. Relevant Maven suites and exact counts | PASS | 300 tests;0 failures/errors/skips |
| 15.1Ã¢â‚¬â€œ12. Compose/build/deploy/health/scrapes/Collector/Tempo/Grafana | PASS | Explicit scoped commands and actual queries |
| 15.13Ã¢â‚¬â€œ14. Real trace delivery and all three server spans | PASS | Stored trace IDs above |
| 15.15-17. Live Learning -> User parents/common trace/correlation | PASS | Section O: actual Tempo spans and matching Loki/OpenSearch records |
| 15.18Ã¢â‚¬â€œ19. JSON IDs plus Loki/OpenSearch ingestion | PASS | Exact completion/event/trace assertions per server |
| 15.20. Positive deployed login/refresh/logout/internal JWT | PASS | Section O: all successful; existing account only; session logged out |
| 15.21. Deployed JWKS response compatibility | PASS | Both public owners unchanged |
| 15.22Ã¢â‚¬â€œ23. No exporter errors in observed window/unrelated preservation | PASS | Log checks and normalized26-container comparison |
| 16. Documentation, commands, limitations and future dependencies | PASS | This record, tracing.md, linked existing docs/examples |
| 17. Git/data/key safety; no commits/push/unrelated repo changes | PASS | Final Git inspection,10 fingerprints,26 unchanged containers |
| Phase3 critical acceptance | PASS | Initial evidence plus section O; noncritical/future-phase limitations remain explicit |

## N. Git status

All four repositories began clean and remain on `develop`. Current HEADs:

| Repository | Unchanged HEAD |
| --- | --- |
| Root | `05833089ec56d8a1136d7af28ece100bfd8192f7` |
| User | `e33853516185ed020cb03d80373c3deba50e584d` |
| Learning | `0f39ac27aea7c9478b239c5775c0c86d4374ab9a` |
| JWKS | `9864becadd3e0a1e884875591bef99bbcd4d775e` |

All task changes are unstaged/uncommitted. Root has Compose, examples, docs,
datasource/baseline-verifier edits, new Collector/Tempo/tracing files and three dirty
submodules. User has application/example/default-assertion edits and new tracing
production/tests. Learning/JWKS additionally modify their POMs. No tracked secret,
RSA key, account record or unrelated repository was edited. Ignored `.log` outputs
and the secret-free ignored preservation snapshot are local verification artifacts.
No commit, push, reset or branch operation was performed. Stop here for Phase3 review.

## O. Authenticated runtime verification follow-up

### Current result: PASS for all ten requested checks

Successful runtime window: **2026-11-11 04:43:47?04:43:59 UTC**
(11:43:47?11:43:59 Asia/Bangkok). Request/log scan window began at
**04:43:49 UTC**. Marker: **`phase3-auth-a4e5371b32444c0e`**.
The earlier 04:27?04:29 UTC attempt could not run authenticated requests because
the file was absent. The file was subsequently supplied; that earlier blocker
is now resolved. Earlier public JWKS traces were not used as authenticated proof.

Before testing, the exact `observability/local-test-credentials.json` path was
confirmed to exist, parse as JSON, contain nonempty string usernameOrEmail/password
fields, and be ignored by Git. Only those two login fields were used. Contents,
identifiers, passwords and token values were never printed. The file's SHA-256
fingerprint matched afterward; neither the file nor ignore rules were changed.
Both this document and tracing.md were read before testing.

| Requested check | Status | Actual evidence |
| --- | --- | --- |
| 1a. Successful User API login | PASS | POST /auth/login returned200, Bearer token contract valid, response correlation preserved |
| 1b. Successful User API refresh | PASS | POST /auth/refresh returned200, refresh token rotated, new access token retained the existing account identity and authenticated the subsequent Learning request |
| 1c. Successful User API logout | PASS | POST /auth/logout returned200 using the rotated refresh token and refreshed access token; verification session cleanup ran in finally |
| 2. Authenticated Learning -> User internal JWT communication | PASS | Learning lookup returned200 and the requested existing user; direct use of the external user JWT on User's /internal/users/{id} returned401, distinguishing the internal service-auth path |
| 3. W3C traceparent propagation across Learning -> User | PASS | Learning continued the supplied sampled W3C parent; User's traceparent-derived callerTraceId/callerSpanId diagnostics matched the distributed trace and outgoing client span in both log backends |
| 4. Server/client/server parent-child relationships | PASS | Learning server -> Learning client -> User server IDs/parents match the actual Tempo data below |
| 5. Shared trace ID across Learning and User | PASS | All core spans use fda09edbe0bd47da8dee413d1fa31ec9 |
| 6. Independent, preserved X-Correlation-ID | PASS | Response and both server completions retain phase3-auth-a4e5371b32444c0e-linked; this value is distinct from the trace ID |
| 7. Trace visibility in Tempo using Grafana datasource queries | PASS | Authenticated Grafana Tempo datasource-proxy trace-by-ID requests returned login, refresh, linked and logout traces |
| 8. Matching traceId/spanId/correlationId in Loki and OpenSearch | PASS | Exact own-server span IDs and shared trace/correlation match Tempo; one completion per expected server in each backend, all status200 |
| 9. No actual verification secrets/PII in observed logs/exported spans | PASS | In-memory scans of retrieved auth traces, matching Loki/OpenSearch records and complete User/Learning/JWKS container logs for the request window found no tested actual passwords, access/refresh tokens, their SHA-256 values, subject IDs, account identifiers, synthetic query/cookie/baggage sentinels or JWT-shaped values; attribute/event checks also passed |
| 10. All APIs and observability services remain operational | PASS | Before/after API readiness, Prometheus and three targets UP, Loki readiness, OpenSearch availability, Fluent Bit running with actual fresh delivery, Collector/Tempo readiness and Grafana database health passed |

### Actual authenticated span evidence

Trace ID: **`fda09edbe0bd47da8dee413d1fa31ec9`**.
Correlation ID: **`phase3-auth-a4e5371b32444c0e-linked`**.

| Service / kind | Span ID | Parent span ID | Name |
| --- | --- | --- | --- |
| learning-api SERVER | `51dbeba2fe661a0c` | `7ae5773e13e14fc7` (supplied remote parent) | http get /api/v1/learning/internal-test/users/{id} |
| learning-api CLIENT | `8ece1a824296f71c` | `51dbeba2fe661a0c` | http get |
| user-learning SERVER | `4c308eeac28b26bf` | `8ece1a824296f71c` | http get /internal/users/{id} |

The controlled incoming header was
`00-fda09edbe0bd47da8dee413d1fa31ec9-7ae5773e13e14fc7-01`.
User's completion diagnostics, parsed from its incoming traceparent, reported
callerTraceId equal to that trace and callerSpanId `8ece1a824296f71c`, matching
the actual Learning CLIENT span. The server spans retain their distinct own IDs.
These checks establish actual wire propagation and parenting, rather than merely
finding separate spans with the same application correlation ID.

The linked trace contains **seven spans total**: the three core HTTP spans above
plus four legitimate JWKS retrieval client/server spans while JWT decoders loaded
keys. Those extra HTTP requests are distinct operations, not duplicated core spans.
Exactly one Learning SERVER, one User-directed Learning CLIENT and one User SERVER
were found in the linked trace.

| Auth operation | Observed trace ID | User SERVER span ID | Total trace spans |
| --- | --- | --- | ---: |
| Login | `c38b460519fe4e1d861fae8b43eb52b3` | `71a6afb4ff987e7b` | 1 |
| Refresh | `77806428501c440fa31a76edda19753b` | `73440c6dbcaf1aee` | 3 (includes JWKS retrieval) |
| Logout | `39d0b57b295c4aee92eb34b3bd692ae0` | `46bf9bb72c21d124` | 1 |

Each operation's trace was queried through Grafana at
`/api/datasources/proxy/uid/tempo/api/traces/<observed-id>`, using existing Grafana
credentials only in memory. Each User SERVER continued its own supplied W3C parent.

### Matching backend evidence and privacy scope

Loki query_range and OpenSearch searches filtered on the exact operation correlation
IDs (`...-login`, `...-refresh`, `...-linked`, `...-logout`). Five expected core server
completions matched in **each** backend: login, refresh, Learning linked server,
User linked server, and logout. All ten paired records had status200 and exact
traceId/spanId/correlationId matches with Tempo. The linked routes remained
`/api/v1/learning/internal-test/users/{id}` and `/internal/users/{id}`; no raw user
ID was needed in the report, logs or exported span attributes.

Privacy checks held actual values only in process memory, including old/new access
and refresh tokens and identity fields returned by the existing-user lookup. Raw
credential/token values and SHA-256 token/password values were scanned without
printing any match or payload. For short account identifiers, exact scalar matching
avoided confusing an ordinary route word with identity data; longer identifiers
were also checked as case-insensitive substrings. A JWT-shaped-value scan covered
unknown internal service JWT values without intercepting or printing Authorization.
Synthetic query/cookie/baggage values were also absent from the inspected telemetry.

Exported span checks rejected sensitive attribute keys including Authorization,
Cookie, full URL/target, username/email/password, exception message and stacktrace.
Retrieved spans had no exception events or status messages. All three application
container log windows passed the same secret/identity/sentinel scans and contained
no exporter failures. The claim is scoped to this flow, retrieved telemetry and
observed time window; it is not an unlimited audit of all historical data or future
application behavior. Response bodies and raw log/trace payloads were not printed.

### Health, sampling and preservation

Before and after the authenticated flow:

- User, Learning and JWKS readiness endpoints returned200.
- Prometheus /-/ready returned200, with all three configured scrape targets UP.
- Loki /ready returned200. Fresh authenticated records were delivered to Loki
  and OpenSearch through the unchanged Fluent Bit pipeline.
- Fluent Bit was running; it has no Docker HEALTHCHECK, so actual delivery was
  verified rather than describing an absent healthcheck as healthy.
- OpenSearch responded without timeout and retained its existing **yellow**
  single-node status. Availability passed; green allocation health is not claimed.
- Collector's internal health extension returned Server available; Tempo /ready
  returned ready; real trace delivery was independently verified through Grafana.
- Grafana /api/health returned200 with database status ok.

The configured sampling probability stayed **0.1 for all three APIs**. Valid sampled
W3C parents selected the controlled requests without enabling production-wide100%
root sampling. No sampling configuration was changed, so nothing needed restoration.

All inspected existing Docker container IDs, images, start times, restart counts,
ports, mounts and network memberships matched before/after, including unrelated
projects. No containers were rebuilt, recreated, restarted or reconfigured. Protected
environment/RSA fingerprints and the credentials-file fingerprint matched. All four
repository statuses/diffs/HEADs were unchanged by the runtime probe. Only this
verification document is retained as an edited work product from this follow-up.
The temporary probe helper was removed; ignored local evidence logs contain only
allowlisted statuses, routes, trace/span/correlation IDs and timestamps, not secrets.

The existing account was used exclusively. No account creation/deletion/update
endpoint or direct database operation was used. Normal login/refresh session state
was created/rotated and then logged out as required; no account/role/profile, other
session, unrelated database, persistent volume or RSA key was modified.

### Execution results and remaining limitations

- The temporary local Python authenticated verifier exited **0**, with **115 successful
  assertion invocations across 91 distinct check labels, zero failures**. It reused the existing HTTP/Docker probe functions;
  no application or checked-in verification code was changed.
- A supplementary Postman GET of the public JWKS readiness endpoint used two inline
  assertions (HTTP200 and JSON status UP), report events disabled, and exited **0**.
  Its first sandboxed attempt could not read registry policy; elevated execution
  succeeded. This was a local public readiness check, not a substitute for the
  authenticated Python/backend assertions.
- No Maven test suite was rerun because no application code changed. The earlier
  300-test result remains the prior implementation evidence, not a new execution.
- No credential/token value was printed, persisted in the evidence logs, placed
  in CLI arguments, or sent to a reporting workspace. No commit, push, reset,
  branch change, deployment or Phase4 work was performed.

**All critical Phase3 acceptance criteria are now satisfied.** Remaining limitations
are unchanged and nonblocking for this phase: browser navigation clicks were not
exercised; retention deletion/crash durability were not tested; Collector queues
remain memory-only; internal tracing endpoints rely on the trusted Docker network;
HA/TLS/authentication, capacity/outage/backup validation and operations dashboards
remain later-phase work. Stop after verification; do not begin Phase4.
