# Phase 0 implementation and verification record

This is the original source/configuration snapshot. Phase 0 has subsequently been
deployed and verified; see [the runtime deployment report](phase0-runtime-verification.md).
The original "not deployed" observations below describe the earlier checkpoint.

Date: 2026-11-09, Asia/Bangkok. Runtime observations below were taken approximately
16:04-16:13 local time. They are snapshots, not a continuous availability claim.

## Changes and boundaries

Implemented: stable service identities, version/environment JSON metadata,
matching OTel resource maps, shared Compose/collector deployment environment,
explicit disabled OTLP exporters, documented local instrumentation controls,
safe health-only endpoint defaults, corrected User query examples, per-module
configuration checks, and the [standards](README.md)/[phase gates](phase-plan.md).

No POM, dependency version, Java version, Dockerfile, authentication/JWKS/internal
JWT/database logic, correlation/request filter, custom encoder Java implementation,
dashboard, retention policy, debug override, deployment key or real `.env` file
was changed. Logback XML adds stable metadata and excludes duplicate context
properties; existing request fields remain. No new backend is deployed.

Initial root and all three submodule working trees were clean. All were on
`develop`; no branch was created/switched and nothing was staged, committed or
pushed. Independent module commits remain:

| Module | HEAD |
| --- | --- |
| User | `e6855457f1a841e3321c35016a32b3a321436203` |
| Learning | `19e16b4cd4010c1653bc099bfaeb245268fdcba4` |
| JWKS | `476df1142de3162d248cf3b497ac8dfdf963f9ac` |

## Source and runtime capability inventory

| Capability | Classification | Evidence / limit |
| --- | --- | --- |
| JSON console and rolling-file logs | IMPLEMENTED; VERIFIED AT RUNTIME for existing builds | Fresh JSON in Loki for all APIs; new identity fields rendered by test application contexts |
| Stable existing service labels | VERIFIED AT RUNTIME | `user-learning`, `learning-api`, `jwks-service` |
| New `serviceVersion` and source environment metadata | IMPLEMENTED; CONFIGURED BUT NOT VERIFIED in deployed containers | New configuration passes binding/rendered-JSON checks; containers were not rebuilt |
| Fluent Bit collection -> Loki | VERIFIED AT RUNTIME | Final last-hour sample: 360 User, 359 Learning, 360 JWKS JSON records, freshest roughly 4-6 seconds old |
| Fluent Bit collection -> OpenSearch | VERIFIED AT RUNTIME | Final query: 91 records per index in the last 15 minutes; latest timestamps around 09:13:25-27 UTC |
| New collector environment configuration | IMPLEMENTED; CONFIGURED BUT NOT VERIFIED as loaded by running collector | Fluent Bit 3.2.10 dry-run succeeded with the shared environment supplied; no reload performed |
| Request correlation | IMPLEMENTED inconsistently; VERIFIED AT RUNTIME | Valid supplied ID replaced by User/Learning; preserved by JWKS; full fix DEFERRED TO FUTURE PHASE 1 |
| Sensitive-data protection | Partial IMPLEMENTED | JWKS field/path/throwable controls; User email/login/token-hash logs and User/Learning raw paths/exception messages remain risks |
| Actuator health | VERIFIED AT RUNTIME | Readiness UP for all APIs |
| Micrometer local metrics | IMPLEMENTED dependency/configuration foundation | Exact live meter inventory NOT VERIFIED; no HTTP metrics exposure or persistent metrics destination |
| Metrics export | Disabled in source baseline | User has OTLP registry; others lack it; Prometheus backend/registry MISSING, DEFERRED TO FUTURE PHASE 2 |
| User trace/span IDs | VERIFIED AT RUNTIME | Both present in all 360 sampled User records in final query |
| Learning/JWKS trace/span IDs | MISSING from sampled runtime records | No tracing bridge in source dependencies; end-to-end instrumentation DEFERRED TO FUTURE PHASE 3 |
| W3C HTTP propagation | Partial IMPLEMENTED | Managed HTTP builders; tests preserve existing headers; actual multi-service span relationships NOT VERIFIED |
| Trace/log OTLP export | Explicitly disabled in source baseline | No active destinations; Collector/Tempo MISSING, DEFERRED TO FUTURE PHASES 3/4 |
| Grafana | VERIFIED AT RUNTIME health; CONFIGURED BUT NOT VERIFIED datasource/dashboard functionality | Health database OK; Loki provisioning exists; authenticated datasource API and UI not exercised |
| Persistence | IMPLEMENTED; configured mounts checked | Named log/checkpoint/Loki/Grafana/OpenSearch/database volumes unchanged; recovery NOT VERIFIED |
| Retention | CONFIGURED BUT NOT VERIFIED | Logback 100MB/30-day/2GB archives, Loki 720h compactor; actual deletion not tested; OpenSearch policy MISSING |

The existing pipeline's `environment` field is added by Fluent Bit. Its presence
in deployed records does not prove the new application metadata is deployed.
Readiness is not an end-to-end login/database/internal-API test. Existing regression
tests cover those contracts with their existing fixtures/mocks, not live databases.

## Docker baseline

Detected project: `springboot_project`, config files in this repository (base plus
debug override). `jp_dev` uses `C:/Personal/japanese-learning/docker-compose.yml`
and was not modified or targeted. Default network: `springboot_project_default`.

| Component | Observed state | Host HTTP endpoint |
| --- | --- | --- |
| User | Running, healthy | `127.0.0.1:8781` |
| Learning | Running, healthy | `127.0.0.1:8782` |
| JWKS | Running, healthy | `127.0.0.1:8783` |
| Fluent Bit | Running, no Docker health check | File-tail inputs, no published ingestion endpoint |
| Loki | Running, HTTP readiness was verified during audit | `127.0.0.1:3177` |
| Grafana | Running, database health OK | `127.0.0.1:3077` |
| OpenSearch | Running, healthy by Compose; cluster yellow | `127.0.0.1:9277` |
| OpenSearch Dashboards | Running, healthy | `127.0.0.1:5677` |

The APIs retain localhost debug ports 5005/5006/5007 only through the optional
override. All inspected containers use Docker `json-file` with empty per-container
rotation options. No driver or volume change was made. Existing runtime API env
does not yet contain the new `DEPLOYMENT_ENVIRONMENT`; native OTel/tracing override
names were absent in the inspected running API environment.

The verifier compares merged configuration against the pre-change base Compose:
ports, mounts, named volumes, networks, limits, restart policies, health checks and
dependencies are identical. Only shared environment entries are added. This is
configuration equality evidence, not a storage-restoration test.

OpenSearch's `status` and `elapsed_ms` mappings are `text`; `@timestamp` is `date`.
Its yellow status is consistent with the existing single-node replica allocation;
all primary shards were active during the audit. No mapping/retention alteration
or cluster repair was attempted.

User's Dockerfile does not explicitly install the `curl` used by its healthcheck,
unlike Learning/JWKS. Current container health passes, but fresh-image availability
of that executable has not been tested; keep this as a rebuild risk, not proof of
a currently broken healthcheck. No Dockerfile change was needed for Phase 0.

## Commands actually run

All commands below were executed, not proposed. Commands needing Docker/Maven
cache access were run with the required permissions. Expanded Compose models,
environment contents, private keys and JWT values were not printed.

| Command / check | Result |
| --- | --- |
| `git status --short` in root and `git -C <module> status --short` before edits | PASS: clean in all four repositories |
| `git submodule status` | Initial sandbox failure: Windows Git shell could not create signal pipe; authorized retry PASS; commits unchanged |
| `java -version` | Java 17.0.19 on host; module target 17; Docker JDKs documented separately |
| `docker compose ls --format json` | PASS: correct project detected by config path |
| `docker compose -p springboot_project --env-file .env -f docker-compose.yml config --quiet` | PASS |
| `docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml config --quiet` | PASS |
| `python observability/verify-baseline.py --runtime` | PASS: configuration/defaults/storage/port checks; live health and log summaries; limits explicitly printed |
| `docker compose -p springboot_project exec -T fluent-bit /fluent-bit/bin/fluent-bit --help` | PASS: confirmed dry-run support |
| `docker compose -p springboot_project exec -T -e DEPLOYMENT_ENVIRONMENT=development fluent-bit /fluent-bit/bin/fluent-bit --dry-run -c /fluent-bit/etc/fluent-bit.conf` | PASS: configuration test successful; running collector not reloaded |
| `docker compose -p springboot_project logs --no-color --since 1h --tail 500 fluent-bit` (aggregate-only output) | PASS: sampled error/retry/HTTP-400 counts all zero; not an outage guarantee |
| `./mvnw.cmd -o test` in User | PASS: 63 tests, zero failures/errors/skips; compilation included |
| `./mvnw.cmd -o test` in Learning | PASS: 78 tests, zero failures/errors/skips; compilation included |
| Additional Learning regression run before assertion correction | FAIL: existing test assumed `ROLE_USER` was first; framework also supplies `FACTOR_BEARER`. Changed user/admin tests to assert role membership, preserving production logic; final suite rerun recorded above |
| `./mvnw.cmd -o test` in JWKS | PASS: 54 tests, zero failures/errors/skips; compilation included |
| Added `ObservabilityBaselineTest` in each module | PASS: defaults, uppercase environment overrides, resource-map binding and absent destinations |
| Updated JWKS `LoggingConfigurationTest` | PASS: release/environment overrides render in JSON; no duplicate context metadata; existing key/HTTP behavior checks retained |
| Parsed final Surefire JSON output with an in-memory Python check | PASS: 45 User, 69 Learning, 58 JWKS JSON records with metadata and no duplicate context fields |
| In-memory Python XML/AST structural check (`python -`) | PASS: console/file metadata definitions agree in all APIs; verifier parses without generating bytecode |
| `git diff --check` in all four repositories | PASS |

The Maven suites were rerun after the final Logback cleanup. Existing tests use
temporary test key fixtures; deployment keys were not regenerated or changed.
Test execution writes normal ignored build/test artifacts, not application data.
The current container images were not rebuilt; no start/stop/recreate/reload,
volume cleanup, dependency installation, Git commit or push was performed.

## Acceptance and remaining risk

| Phase 0 criterion | Result | Evidence |
| --- | --- | --- |
| Inspect all modules, runtime/env/infra and dependency compatibility | PASS | Standards matrix, source/config review, runtime inventory |
| Preserve existing canonical service identities and routing | PASS | Runtime labels unchanged; source JSON checks |
| Apply version/environment metadata and safe configuration defaults | PASS | Binding/JSON checks, base/debug configuration validation |
| Define all required request/resource concepts without premature filter migration | PASS | Standards field table and Phase 1/3 contracts |
| No destinationless exporter enabled by new defaults | PASS | All three exporter flags false; no new endpoints/dependencies |
| No newly public sensitive Actuator endpoints | PASS | Health-only merged settings and source defaults |
| Preserve auth/JWKS/internal JWT contracts | PASS for regression scope | Existing module suites pass; live authenticated E2E NOT VERIFIED |
| Preserve networks, volumes, ports and runtime containers | PASS | Merged-model comparison; no lifecycle commands; current health |
| New metadata/collector config active in deployed images/processes | NOT VERIFIED | Deliberately not deployed/reloaded in Phase 0 |
| Complete metrics/traces/retention/alerts | NOT VERIFIED; outside Phase 0 | Explicit later-phase gates |
| Real secrets/env files/deployment keys untouched; no commit/branch changes | PASS | Only examples edited; final Git inventory and unchanged module commits |

Phase 1 is ready for review with no identified implementation blocker. Production
rollout is not approved by this baseline. Phase 1 must address correlation continuity,
filter ordering/async/final-status behavior, sensitive logging, numeric schema/index
migration, and regression tests. Runtime exporter/metric inventory, authenticated
Grafana functionality, retention enforcement, outages and full multi-service traces
remain explicitly unverified or deferred.

## Changed-file inventory and final Git state

Root modified files: `.env.example`, `.env.user-api.example`,
`.env.learning-api.example`, `.env.jwks-api.example`, `docker-compose.yml`,
`observability/fluent-bit/fluent-bit.conf`, `observability/grafana/README.md`,
`observability/opensearch/README.md`.

Root added files: `observability/README.md`, `observability/phase-plan.md`,
`observability/phase0-baseline.md`, `observability/verify-baseline.py`.

In each submodule, modified `.env.example`, `src/main/resources/application.properties`,
and `src/main/resources/logback-spring.xml`; added
`src/test/java/com/japaneselearning/<user|learning|jwks>/observability/ObservabilityBaselineTest.java`.
JWKS additionally modifies `src/test/java/com/japaneselearning/jwks/logging/LoggingConfigurationTest.java`.
Learning additionally modifies `src/test/java/com/japaneselearning/learning/security/jwt/user/JwtAuthenticationTest.java`
to remove an ordering assumption exposed by regression testing.
No tracked files were deleted. Temporary edit helpers were removed, not retained
as implementation artifacts.

Final state: root has the above modifications/new files and lowercase `m` for
all three dirty submodules. Each submodule has only its listed changes. All four
repositories remain on `develop`, module HEADs match the table above, and no
changes are staged. Review/commit each independent repository separately later.
