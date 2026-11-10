# Phase 2 implementation and runtime verification

Date: 2026-11-10, Asia/Bangkok. Deployment began around 08:12 UTC / 15:12 local;
runtime verification continued after the controlled JWKS restart around 08:22 UTC.
See [metrics.md](metrics.md) for the maintained architecture/configuration contract
and PromQL, [Phase 1](phase1-verification.md) for the preceding logging deployment.

## A. Executive summary

**Implemented, tested and deployed:** Boot-managed Prometheus registries in all
three services, protected scrape connectors, bounded security counters, HTTP
histograms, Prometheus storage, and an additional Grafana datasource.
All **291 tests passed, zero failures/errors/skips**. All three application
containers and Prometheus are healthy; all three scrape targets are UP.

Live HTTP/JVM/CPU/executor/pool meters, p50/p95/p99 queries, negative security
counters, Grafana proxy querying, both logging backends, public JWKS compatibility
and historical samples across an application restart were observed.

Runtime acceptance is **partial**: successful login/logout, successful refresh,
authenticated Learning -> User calls/client meters and their end-to-end
correlation were **NOT VERIFIED in this phase**. The user-specified
`observability/local-test-credentials.json` did not exist when checked, including
before final reporting. No credentials were invented/persisted, and no account
was created, modified or promoted. Existing automated auth/internal JWT tests and
the real managed-client metrics test passed; these do not substitute for live auth.

No Phase 3–6 infrastructure or instrumentation was implemented.

## B. Changes by repository

All four working trees were clean before implementation. No pre-existing local
changes in this root or the three Spring repositories were discarded.

### All three service repositories

- `pom.xml`: add only `io.micrometer:micrometer-registry-prometheus`, with version
  managed by the existing Boot parent. No Boot/Java/logging/tracing upgrades.
- New `src/main/java/com/japaneselearning/<service>/metrics/MetricsConfiguration.java`:
  stable common tags, one version-info gauge, URI budgets, security-counter bean.
- New `metrics/MetricsEndpointConfiguration.java`: opt-in extra Tomcat scrape
  connector and highest-priority security chain; deny scrape on application port.
- New `metrics/SecurityMetrics.java`: seven bounded operation/result counter pairs.
- Existing `logging/filter/RequestLoggingFilter.java`: notify security metrics
  inside the existing atomic final-completion guard; successful scrapes use DEBUG
  like health probes. No second HTTP timer/log or changed response/auth decision.
- `src/main/resources/application.properties`: listener/export defaults and fixed
  server/client SLO buckets. Standalone Actuator exposure remains health by default.
- `.env.example`: document optional standalone scrape configuration, no secrets.
- New `src/test/java/.../metrics/MetricsIntegrationTest.java`, `SecurityMetricsTest.java`.

### User

Also adds `metrics/HikariPoolMetricsTest.java` under test sources. Existing User
authentication, authorization, refresh, internal JWT decoder and HTTP behavior
are unchanged. No datasource URL, credentials, pool size, timeout or signing key
configuration changed.

### Learning

Also adds test `HikariPoolMetricsTest.java` and `InternalClientMetricsTest.java`.
`ServiceClientConfig` and `UserServiceClient` production code did not require any
change: their managed builder and URI template already support correct observations.
JWT attachment, correlation interceptor, connect/read timeouts and existing error
translation remain intact.

### JWKS

Adds the same registry/connector/counter configuration without any JDBC dependency
or pool. No controller, endpoint schema/path, issuer/audience, keys/key IDs,
cache contract or application authorization rules changed.

### Root

- `docker-compose.yml`: three private listener settings, new Prometheus service
  and named volume, one read-only Grafana datasource mount. Existing ports,
  networks, persistent mounts and dependencies remain unchanged.
- New `observability/prometheus/prometheus.yml` and Grafana datasource
  `observability/grafana/provisioning/datasources/prometheus.yml`.
- `.env.example`, three `.env.<service>.example` files: metrics settings and
  loopback-only optional Prometheus host port. No real environment files edited.
- `.gitignore`: ignore only the explicitly supplied local test-credentials path.
  The file itself was not created.
- `observability/verify-baseline.py`: continue preservation checks, allowing only
  reviewed Phase 2 additions; keep base/debug and disabled-OTLP checks.
- New `observability/verify-metrics.py`: repeatable safe live verification, optional
  existing ignored credentials, logout of its own refresh session when created.
- Updated `observability/README.md`, `structured-logging.md`, `grafana/README.md`;
  new `metrics.md` and this report. Historical Phase 0/1 reports were preserved.

## C. Actual metrics inventory and labels

Registry versions resolved by existing parents: **User Micrometer 1.17.1**,
**Learning/JWKS 1.17.2**. Boot remains 4.1.1 / 4.1.2 / 4.1.2; Java target 17;
Docker JVMs 21 / 21 / 17. Encoder 8.1 and existing trace dependencies are unchanged.

The following names and label sets were actually queried after deployment:

| Meter | Observed scope | Label keys beyond metric name |
| --- | --- | --- |
| `http_server_requests_seconds_count` / buckets | All three; 13 count series in initial sample | environment, error, exception, instance, job, method, outcome, service, status, uri; buckets also le |
| `http_client_requests_seconds_count` / buckets | Live Learning -> JWKS; automated Learning -> User | client_name, environment, error, exception, instance, job, method, outcome, service, status, uri; buckets also le |
| `jvm_memory_used_bytes` | All three; 24 initial series | area, environment, id, instance, job, service |
| `jvm_gc_pause_seconds_count` | GC events observed across all three; 4 initial series | action, cause, environment, gc, instance, job, service |
| `jvm_threads_live_threads` | All three | environment, instance, job, service |
| `process_uptime_seconds`, `process_cpu_usage`, `system_cpu_usage` | All three | environment, instance, job, service |
| `executor_active_threads` | All three, applicationTaskExecutor | environment, instance, job, name, service |
| `hikaricp_connections_active` / idle/pending/max | User/Learning only | environment, instance, job, pool, service |
| `hikaricp_connections_acquire_seconds_count` | User/Learning only | environment, instance, job, pool, service |
| `jdbc_connections_active` | User/Learning only | environment, instance, job, name, service |
| `app_security_events_total` | 21 initialized bounded series | environment, instance, job, operation, result, service |
| `app_build_info` | Three constant identity gauges | environment, instance, job, service, version |

Counts above are samples, not permanent inventory limits. JVM's `id` denotes
bounded memory pool identity, not a user/request ID. Prometheus adds job/instance;
applications add only service/environment as common tags. Version is on one info
meter rather than every series. No correlation/trace/session/account/token labels.
Further standard metric families and platform limits are described in `metrics.md`.

## D. HTTP metrics and cardinality

Framework servlet observations supply counts, duration sums/max and histogram
buckets. Fixed boundaries: 5/10/25/50/100/250/500 ms, 1/2.5/5/10 seconds, +Inf.
No manually duplicated HTTP timers or client quantile summaries were added.
Real PromQL `histogram_quantile` at **0.50, 0.95 and 0.99** returned finite results
for all three services. Precision is limited by bucket interpolation and the
10-second upper finite bucket; idle windows can return NaN.

Tests sent distinct sensitive IDs to the same route and observed one templated
timer with count 2; async success recorded once. Framework fallback labels are
bounded. Both HTTP meter families have an additional 100-distinct-URI budget.
Query strings/raw paths, correlation IDs and credentials were absent from tested
expositions. All three exposed scrape paths returned **403 on application ports**.
Other Actuator/business paths returned **403 on private scrape ports**.
Real-container tests also rejected an authenticated request to the application
scrape path. No broad Actuator permitAll rule was introduced.
Live forged Forwarded/X-Forwarded-Port/X-Forwarded-For headers could not bypass
application-port scrape denial in any of the three services.

## E. JVM and database evidence

Prometheus stored JVM heap/nonheap, GC, thread, CPU and uptime meters for all
three services. `applicationTaskExecutor` metrics were present in all three.
No promise is made for arbitrary unregistered/background executors or platform
OS metrics not supplied by the runtime.

Hikari active/idle/pending/max and acquisition meters were queried for exactly
User and Learning. Both existing pools reported maximum 10; sampled acquisition
counts were User 4 and Learning 2. These are existing pool settings, not changes.
Actual Hikari tracker tests used a JDBC stub and verified borrow/return/acquisition
metrics without starting or adding a real database. Pool snapshots cache values
for one second; tests wait for refresh rather than weaken idle-count assertions.
JWKS correctly has no Hikari/JDBC meters.

## F. Security and internal client metrics

The exact exclusive classification and increment owner are documented in
`metrics.md`: terminal login/refresh HTTP result takes priority, then other 401
authentication/internal-authentication or 403 authorization rejections. The
existing final-completion atomic guard prevents async/error redispatch duplication.
Counters contain only fixed operation/result labels, with no account/token data.
They count HTTP results rather than individual provider attempts or token issuance.

Live nonexistent-account login, invalid refresh and anonymous internal requests
produced their expected rejection statuses and incremented the respective failure
counters. Public scrape denials exercise the authorization-rejection path.
No accounts were created or changed. Successful auth/refresh counter increments
are covered by instrumentation contracts only as applicable; live positive flows
remain NOT VERIFIED without the specified credentials file.

The managed Learning client test made two successful and one upstream-404 real
HTTP exchanges through `ServiceClientConfig`/`UserServiceClient`: exactly three
standard client observations, status counts 2/1, URI `/internal/users/{id}`, no raw
UUID/correlation/JWT labels; correlation header retained. Existing service-token
and timeout tests still pass. Live **Learning -> User** client metrics remain
NOT VERIFIED; the public Learning -> JWKS diagnostic call did produce a live
standard client timer and shared correlation in both Loki and OpenSearch.

## G. Prometheus deployment and persistence

- Image: `prom/prometheus:v3.13.5`, explicitly versioned LTS, successfully pulled.
- Targets: `user-api:9091`, `learning-api:9091`, `jwks-api:9091`; all **UP**, lastError
  empty in sampled target API output; observed scrape durations around 8–11 ms.
- 15s interval, 5s timeout; 20k sample and bounded label limits.
- Named volume `springboot_project_prometheus_data`; 15d retention and 2GB flag
  (Prometheus reports 2GiB). Retention size is not a hard disk quota.
- Non-root/read-only root filesystem, 512MiB memory, one CPU, PID limit128,
  unless-stopped restart, native wget readiness health check passed.
- Host endpoint: loopback-only 9090; private API scrape ports never published.
- `promtool check config /etc/prometheus/prometheus.yml`: PASS.

A controlled restart of **only JWKS** verified that pre-restart HTTP samples were
queryable at the exact original timestamp afterward, while new JVM start time
was subsequently scraped and all targets returned UP. Prometheus stayed running
with its existing process/volume. This verifies history survives an **application**
restart, not Prometheus crash recovery, disk-loss restore or 15-day deletion.

Network trust is the existing private Docker bridge and trusted host/Docker
administrators. No new shared password, public scrape, management-port forwarding,
Collector, Tempo, remote-write receiver or public Actuator exposure was introduced.

## H. Grafana integration

Existing Grafana administrator credentials were read only in memory from the
effective Compose model; no values were printed. Authenticated API checks showed
Loki still default and healthy, Prometheus non-default and healthy. A query through
`/api/datasources/proxy/uid/prometheus/api/v1/query?query=up` returned all three
targets with value1. Existing data/provisioning were retained. This Grafana instance
had Loki and Prometheus datasources; OpenSearch remains the existing separate
OpenSearch/Dashboards integration. No existing datasource was removed or replaced,
and no new dashboard/alert was implemented.

## I. Automated checks and troubleshooting

Final command from each module:

```powershell
.\mvnw.cmd -o test
```

| Module | Tests | Failures | Errors | Skips | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| User | 99 | 0 | 0 | 0 | PASS |
| Learning | 115 | 0 | 0 | 0 | PASS |
| JWKS | 77 | 0 | 0 | 0 | PASS |
| Total | 291 | 0 | 0 | 0 | PASS |

New tests exercise real Tomcat connectors/security/Actuator exposition, shipped
configuration binding, JVM meters, histograms, templated routes, async/error
recording, bounded counter semantics, Hikari tracking and the actual managed
Learning client. Existing JWT/JWKS, internal JWT, correlation/MDC and safe JSON
logging tests remain enabled and passing.

Focused runs used `-Dtest=MetricsIntegrationTest,SecurityMetricsTest` and expanded
selections adding `InternalClientMetricsTest,HikariPoolMetricsTest`. Initial
compilation used `.\mvnw.cmd -q -DskipTests compile` to resolve registries.
Development failures were corrected before final suites: Boot4 API is
`addAdditionalConnectors`, duration binding needs `2500ms` rather than `2.5s`,
SimpleMeterRegistry needs explicit close, Learning test resources shadowed main
configuration, client fixtures needed the full DTO, and Hikari cached gauges need
a bounded wait. One unquoted PowerShell Maven property was parsed incorrectly;
the unnecessary property was removed. No assertions were weakened and no failed
test was skipped. Docker packaging uses its existing `-DskipTests` after the full
local suites; this is not a claim that the image build ran tests.

Python verifier syntax and root/module `git diff --check` were checked. Base and
debug Compose config plus the preservation verifier passed.

## J. Deployment/runtime commands and operational findings

Commands actually executed (Compose mutations always specify this project):

```powershell
docker compose ls --format json
docker compose -p springboot_project ps --format json
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml config --quiet
python observability/verify-baseline.py
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml pull prometheus
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml build user-api learning-api jwks-api
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build --wait --wait-timeout 120 jwks-api
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build --wait --wait-timeout 120 user-api learning-api
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build --wait --wait-timeout 90 prometheus grafana
docker compose -p springboot_project exec -T prometheus promtool check config /etc/prometheus/prometheus.yml
python observability/verify-metrics.py --credentials observability/local-test-credentials.json
python observability/verify-baseline.py --runtime
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml restart --no-deps --timeout 45 jwks-api
```

These final commands passed. Baseline's generic NOT VERIFIED footer means that
script does not itself test meter inventory/Grafana authentication; the separate
successful checks above provide that evidence. The reusable metrics verifier
prints NOT VERIFIED for credential-dependent checks and exits0 only after its
available checks pass; exit0 must not be read as authenticated-flow verification.
Successful run marker: `phase2-030880416d3343e8`.

Additional read-only command/query families: `docker ps -aq`, `docker inspect`,
captured `docker compose ... config --format json`, captured `logs --since`,
private `exec prometheus wget` scrape/denial probes, Python HTTP PromQL/targets/
retention flags, Loki query_range, OpenSearch searches and Grafana API checks;
Git status/branch/HEAD/diff and source/config reads. No raw credentials, keys,
JWTs or credential-bearing Compose model were printed.

A local Postman denial check with `--no-report-events` reported **two passed
assertions** (403 and correlation header) but CLI exit1 because request mode
fails on 4xx even when those assertions pass. This is recorded as the observed
expected-denial behavior, not a successful exit0 run. Python exact-status probes
and real-container automated tests independently passed. Sandboxed CLI help
initially could not read its registry policy; elevated read-only help succeeded.
The first persistence probe selected a concrete path instead of the server route
template and found no series; no restart occurred in that failed attempt. The
corrected aggregate/history probe passed.

### Containers and preservation

Recreated existing containers: `springboot_project-user-api-1`, `-learning-api-1`,
`-jwks-api-1`, `-grafana-1`. Added `springboot_project-prometheus-1`. JWKS also had
one deliberate restart for the persistence check, without another recreation.
Three APIs and Prometheus are healthy; Grafana is running with API health OK
(no configured Docker healthcheck).

Before/after comparison proved **25 unrelated existing containers unchanged**,
including all **16 `jp_dev` containers**, checking IDs/images/start times/restart
counts/ports/mounts/networks. Fluent Bit, Loki, OpenSearch, databases and migration
containers were not recreated. Exactly one Prometheus volume and one read-only
Grafana datasource mount were added. All original ports, networks and storage
mounts were preserved; **10 environment/key fingerprints matched**.

Compose warned that the existing Grafana data volume lacked Compose ownership
metadata. It was reused; no volume was deleted/recreated or ownership metadata
changed. This pre-existing volume provenance warning is not a data-loss event.
OpenSearch remained yellow as in Phase0's single-node setup.

### Logging compatibility

All three services produced fresh records ingested into Loki and OpenSearch.
Valid response correlation IDs were retained; Learning -> JWKS shared exactly
one final completion per service in both backends. Authenticated Learning -> User
is explicitly not substituted by this check. Framework-owned User trace/span
logging remains available. No unexpected OTLP export errors or successful scrape
INFO noise were found in checked application logs; tested secret sentinels were
absent from logs and metrics.

Fluent Bit had **four transient OpenSearch flush warnings** at 08:12:24,
08:12:39, 08:12:44 and 08:22:04 UTC. Each exact chunk succeeded on **retry1** at
08:12:34, 08:12:45, 08:12:52 and 08:22:14 (6–10 seconds later). Fresh ingestion
passed. A strict diagnostic asserting no flush warnings failed and triggered this
investigation; it was not hidden or treated as pipeline loss. Root cause was not
established. No collector/backpressure/storage setting was changed to mask it.
Prometheus had no error-level log entries in the checked window. Long-term
durability/backpressure investigation remains Phase6 work if warnings recur.

## K. Cross-project JWKS compatibility

`japanese-learning` requires **no changes**. Public User/Learning JWKS bodies,
RSA key material/key IDs, content types and cache headers matched the pre-rollout
snapshot exactly, including after the controlled restart. Existing API ports,
service DNS/network membership, issuer/audience validation and application
security rules remain. The additional unpublished scrape listener changes no
consumer request/response contract. Read-only review of its .NET
`JwksConfigurationRetriever` and Quarkus OIDC JWKS configuration confirmed the
unchanged standalone JWKS contract. Its root had pre-existing dirty `angular`
and `quarkus` pointers; nothing there was modified. All `jp_dev` containers were
unchanged, so no separate consumer implementation prompt is needed.

## L. Known limitations and phase boundaries

- No local credentials file was available at the supplied path. Positive live
  auth/logout/refresh and Learning -> User JWT/client/correlation checks remain
  NOT VERIFIED; run the documented verifier with an existing ignored file later.
- Runtime non-admin role-based403 remains the prior Phase1 gap. Published metrics
 403 denial and real test-container role rejection were verified; they are distinct.
- Private Docker bridge and privileged host trust are explicit; no per-scraper
  TLS/password was introduced. Review before exposing the network to untrusted
  workloads. Metrics data must not be republished as a public endpoint.
- Histograms interpolate fixed buckets; idle queries may be NaN. Scrape route
  traffic contributes to service-wide HTTP metrics; filter it for business latency.
- Four recovered OpenSearch flush warnings and existing yellow health/provenance
  warnings are documented above. No zero-warning/indefinite availability claim.
- App-restart history was verified; Prometheus crash/restart restore, retention
  deletion, load/outage recovery, quotas/backups and alerts were not tested.
- Full distributed tracing, OTel Collector/Tempo, exemplars, operations dashboards,
  alerting and storage/security overhaul remain Phase3–6. No OTLP destination was
  activated. No trace IDs were fabricated or added to metric labels.

## M. Acceptance criteria

| Requirement | Status | Evidence |
| --- | --- | --- |
| Inspect/preserve Phase0/1 implementation | PASS | Source/docs review, full regression and preservation checks |
| Uniform Micrometer/Prometheus identity/naming | PASS | Managed registries, actual labels/info gauge across all services |
| HTTP count/status/outcome/duration and aggregatable histograms | PASS | Real requests, templated routes, live buckets/p50/p95/p99 |
| JVM/process/system and supported executors | PASS | Stored meters all three, actual applicationTaskExecutor inventory |
| Hikari/JDBC where applicable | PASS | Live User/Learning pools; real tracker tests; JWKS intentionally N/A |
| Bounded security metrics without double counting | PASS | Exclusive terminal hook/tests and live rejection counters |
| Learning -> User client instrumentation | PASS | Real managed-client integration test, exactly three exchanges |
| Deployed authenticated Learning -> User client/JWT/correlation | NOT VERIFIED | Specified credentials file missing |
| Successful deployed login/logout/refresh | NOT VERIFIED | Specified credentials file missing; no accounts created/modified |
| Secure scrape exposure, health/API rules preserved | PASS | Main port403/private scrape200; private other endpoints403; real security tests |
| Prometheus deployment/storage/retention/health | PASS | Explicit image, native validation, three targets UP, app-restart history |
| Grafana datasource/query integration | PASS | Authenticated datasource health and proxied three-target UP query |
| Existing logs/correlation/trace metadata protected | PASS | Regression tests, fresh both-backend ingestion; live Learning -> JWKS correlation |
| JWKS consumer compatibility and jp_dev preservation | PASS | Exact public contract comparison, read-only consumers, 16 unchanged containers |
| Tests without weakened/skipped regressions | PASS | 291 passing tests, zero skips |
| No unexpected OTLP export errors/Phase3–6 work | PASS | Disabled exports and observed logs; no future infrastructure |
| Documentation and safe Git behavior | PASS | Contract/report/examples; no commit/push/reset/branch operation |

Phase2 implementation/deployment is ready for review with the explicit runtime
credential gaps above. Do not represent the gaps as verified or begin Phase3
without review.

## N. Git state

Root/submodules began clean. HEADs remain at the initial values:
root `8c8659976efd42beff055df6756dcded5752512a`,
User `fcf000aa3388bd6fc498053c806fa582a5a8a8d8`,
Learning `87d7eb28377f0258fd2f5371a71ec2b0a522aa60`,
JWKS `1ab00362e725bb5ec7f64a3380b0464c19db6d85`.
All four branches remain `develop`. All Phase2 changes remain unstaged/uncommitted;
new metrics/config/test/documentation files are untracked. Root shows dirty
submodules because their working files changed, not because HEADs moved.
No real `.env`, key, private credentials file or unrelated repository was written.
The temporary secret-free deployment snapshot was removed after comparison.
