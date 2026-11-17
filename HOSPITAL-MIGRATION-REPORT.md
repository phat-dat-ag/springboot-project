# Hospital Management System migration report

The Learning module has been replaced by the Hospital API technical foundation.
No Hospital business entities, repositories, seed data or fake migrations were
created. Source changes are local and uncommitted. No remotes were changed, and
no Docker containers, networks, volumes or persistent data were operated.

## Naming and directory changes

| Previous identifier | Current identifier |
| --- | --- |
| Project branding | Hospital Management System / `hospital-management` |
| Writable Maven group and base package | `com.hospitalmanagement` |
| User artifact/application/service | `hospital-user-api` |
| Parent-managed JWKS application/service | `hospital-jwks-api` |
| `springboot-learning-api` | `springboot-hospital-api` |
| `com.japaneselearning.learning`, intermediate `com.hospitalmanagement.learning` | `com.hospitalmanagement.hospital` |
| Learning application entry point | `HospitalApiApplication` |
| Learning controller and identity DTO | `TechnicalAuthenticationController`, `AuthenticatedCallerResponse` |
| Learning service identity in telemetry | `hospital-api` |
| Old development Compose project | `hospital_dev` |
| Default development bridge | `hospital-network` |
| User MySQL database | `hospital_user_db` |
| Hospital PostgreSQL database | `hospital_db` |

`REBRANDING-CHANGES.json` contains the complete per-file rename mapping, including
142 existing Java files, module/environment moves, and metrics TLS configuration
filenames. User now has 79 Java files; Hospital has 65, including two new test
classes. Module Git histories and remote URLs have not been rewritten.

## Removed application domain and new foundation

The retired module had no Learning entities, repositories, jobs, seed data or SQL
migrations. Its domain-named controller/DTO and old endpoint mappings were
removed. All production packages moved to the Hospital namespace. Reusable
security, clients, exceptions, validation, logging, metrics and tracing remain.
Infrastructure regression tests were adapted rather than discarded.

Hospital has three explicitly technical GET endpoints:

- `/api/v1/hospital/technical/authentication`: authenticated subject/roles/issuer,
  without exposing a token.
- `/api/v1/hospital/technical/users/{id}`: existing internal User lookup.
- `/api/v1/hospital/technical/jwks`: existing public-key diagnostic client.

All require USER or ADMIN. The former public integration diagnostic is no longer
public or available at its old route. Swagger/OpenAPI and health/readiness remain
public. The new negative-route test verifies retirement of the old routes and
absence of an unimplemented patient route. No clinical functionality is implied.

## PostgreSQL and Flyway

Hospital uses the PostgreSQL JDBC driver, Spring Data JPA, Hikari, and Spring
Flyway with PostgreSQL support. Credentials are environment supplied. Pool
defaults are minimum 2, maximum 10 and acquisition timeout 30000 ms.

The canonical migration directory is
`springboot-hospital-api/src/main/resources/db/migration/`. It contains only a
placeholder. The obsolete root migration placeholder was removed. Compose's
`flyway-postgres` mounts this same source and must succeed before Hospital starts;
Spring Flyway also supports standalone packaged startup. There are no business
migrations to validate against a real database yet. Hibernate uses `validate`,
SQL initialization is disabled, and Flyway clean is disabled.

PostgreSQL retains port mappings, credential-based readiness checks, and a
persistent `hospital_dev_postgres_data` volume. User remains on MySQL with its
existing real migrations. No database conversion or data migration was attempted.

## Docker and environment configuration

Compose now names its project `hospital_dev` and default network
`hospital-network`. API services/images are `hospital-user-api`, `hospital-api`,
and `hospital-jwks-api`, with locally built image names under
`hospital-management/`. Default generated container names follow
`hospital_dev-<service>-1`. Named volumes receive the `hospital_dev_` prefix;
Hospital logs use `hospital_dev_hospital_api_logs`. Other storage volumes retain
their functional names under the new project prefix.

Build contexts, env files, URLs, log mounts, Fluent Bit paths, debug settings and
Compose overlays reference the new module/service. Existing effective host ports
and security restrictions were preserved. JWKS still builds from its untouched
submodule and Dockerfile. Its runtime identity is overridden using supported
`SPRING_APPLICATION_NAME` and `APP_NAME` environment variables in the parent.

| Previous environment setting | Replacement |
| --- | --- |
| `.env.learning-api[.example]` | `.env.hospital-api[.example]` |
| `LEARNING_API_*` | `HOSPITAL_API_*` (including debug, logging and migration path) |
| `LEARNING_INTERNAL_JWT_*` | `HOSPITAL_INTERNAL_JWT_*` |
| `LEARNING_JWT_JWK_SET_URI` | `HOSPITAL_JWT_JWK_SET_URI` |
| `LEARNING_SIGNING_KEYS_DIR` | `HOSPITAL_SIGNING_KEYS_DIR` |
| PostgreSQL database value | `POSTGRES_DB=hospital_db` |
| Compose project | `COMPOSE_PROJECT_NAME=hospital_dev` |
| Hospital pool configuration | `HOSPITAL_DB_POOL_MAX_SIZE`, `HOSPITAL_DB_POOL_MIN_IDLE`, `HOSPITAL_DB_CONNECTION_TIMEOUT` |

Filled local env files were updated outside JWKS. They remain ignored. Credential
values are not included in this report or the audit artifacts. New setups must
still supply credentials and the existing signing/public key configuration.

## Security and protected exceptions

User authentication endpoints and business behavior remain unchanged. Hospital
retains issuer/signature/timestamp/required-claim verification, numeric role
mapping, short-lived RS256 internal JWTs, `internal+jwt`, fresh jti values, and
separate signing keys. The internal Java authority was renamed to
`SERVICE_HOSPITAL` in User's decoder chain and tests; this is not a token claim.

The following strings must remain to use the unchanged shared publisher and
existing trust configuration:

- Internal issuer/subject `learning-service`.
- JWKS owner `LEARNING` and `/api/v1/jwks/learning`.
- Existing `learning-rsa-v1` key ID, test key IDs, and key filenames/mount paths
  under `data/keys/learning` and `/run/keys/learning`.
- Existing external User-token issuer, independently configured by `JWT_ISSUER`.

These are compatibility contracts rather than application branding. They appear
in Compose, env templates, application properties, security documentation and
regression tests. Keys were neither generated nor rotated. Caller metadata now
uses Hospital service names; those headers remain self-reported diagnostics.

Renaming the protected owner requires a separate coordinated JWKS migration and
all consumer updates. No change to another consuming repository is needed for
this implementation. The other local repository's `.gitmodules` and JWKS HEAD
were inspected read-only; no content there was modified.

The Hospital submodule URL in `.gitmodules` intentionally remains
`https://github.com/phat-dat-ag/springboot-learning-api.git`. Renaming that remote
would violate the task. Its local section/path now use the Hospital name.

## Shared JWKS integrity

Verified before and after:

| State | Unchanged value |
| --- | --- |
| Checked-out HEAD | `ce012c84f1a1acc8f9b3a0a3039906b37be3332c` |
| Working tree | Clean |
| Parent HEAD/index gitlink | `e9b90c31dfa311e0121285c8b7caa37c09cf4287` |
| Submodule path and URL | Unchanged |

The difference between its checked-out HEAD and parent gitlink existed before
this work. `git submodule status` therefore still shows `+` for JWKS. It was not
corrected. A fresh checkout at the recorded gitlink can differ from this local
JWKS checkout; runtime equivalence of those revisions is not established here.
No Maven command was run against JWKS because Maven would write into its tree.

The Hospital gitlink path rename is staged at its original commit
`8cb37c6bb66ee453316f0f3ecbf8af5e9ba63309`. Its parent local submodule registration
was initialized at the existing URL, without fetch or checkout. Source edits
inside User and Hospital are unstaged/uncommitted, and parent `.gitmodules` edits
remain unstaged. Nothing was committed or pushed.

## Observability and legacy audit

Prometheus targets/labels, Grafana dashboard and alert queries, Fluent Bit log
filenames/filters, OpenSearch index prefixes, Tempo resource identity, secure
metrics sidecars, verification scripts and documentation now use Hospital names.
Correlation, W3C propagation, sampling, retention, bounded queues/spools, privacy
filters, and exporters were retained.

Run `python audit_hospital_references.py` for the recursive inventory. Findings
are recorded by file/line/category in `HOSPITAL-LEGACY-REFERENCES.json`, without
recording complete lines or credentials. No unclassified active legacy references
remain. Exceptions include the protected contracts above, the unchanged remote
URL, protected JWKS source/package references, the negative-route assertion, and
audit/history artifacts. The shared tree's legacy identifiers remain untouched.

Ignored historical runtime captures under `observability/phase6-evidence/` and
`.phase3-state.json` retain their original evidence. Git metadata, generated
targets/logs, IDE files, private keys and persistent data are excluded from the
active-source audit. They are not deployment configuration. Existing observability
measurement documents predate this migration; updated naming in those documents
does not establish new runtime results.

## Executed validation

| Check | Result |
| --- | --- |
| Root `mvn validate` | Passed for User, Hospital and aggregator |
| Root `mvn compile` | Passed |
| Root `mvn test` | Passed: User 105 tests; Hospital 125 tests, including 1 skipped |
| User internal JWT regression rerun | Passed: 22 tests |
| Observability offline unit tests | Passed: 15 tests |
| Phase 6B offline safety tests | Passed: 14 tests |
| `python validate_rebranding.py` | Passed |
| Base/debug/secure-production/notification Compose rendering | Passed |
| Java package/path/import namespace checks | Passed |
| PostgreSQL credential/URL consistency and Flyway safeguards | Passed statically |
| Legacy-reference classification | Passed; see inventory |
| Root and writable submodule diff whitespace checks | Passed |
| `git submodule status` | Passed; pre-existing JWKS mismatch preserved |

Initial test failures from endpoint migration were corrected and the reactor
rerun successfully. Maven dependency-cache writes and offline temporary-directory
tests needed sandbox escalation; those reruns passed.

The opt-in PostgreSQL startup/Flyway test was **not executed**: no real database
was started or configured for it. Normal web tests exclude database auto-configuration.
The client/security/tracing tests use local HTTP fixtures, not live deployed User
or JWKS services. Docker image builds, live PostgreSQL/Flyway migration validation,
container readiness, production certificates and backend telemetry ingestion
remain unverified. No deployment/runtime success is claimed.

## Manual steps before rebuilding

1. Review the source changes inside User and Hospital and their unchanged remotes.
   Before publishing, commit those child changes yourself and update the parent
   pointers; a parent commit alone cannot include uncommitted child source edits.
   Stage the matching `.gitmodules` change when recording the path rename.
2. Keep JWKS untouched. Review its pre-existing pointer mismatch separately rather
   than accidentally staging a new JWKS gitlink.
3. Manually remove only the obsolete development Docker resources you own, as
   planned. Preserve the existing signing PEM files before deleting development
   data. No new keys are supplied by this migration.
4. Review ignored root env files or create them from the four templates. Confirm
   `hospital_db`, `hospital_user_db`, credentials, issuer agreement, mounted PEM
   paths and matching key IDs/owners. Remove obsolete shell-level overrides.
5. If using the optional secure-production overlay, supply authorized certificates
   with the new service DNS names/SANs and per-service TLS directory names. Compose
   syntax validation does not validate certificate material.
6. Run `mvn test` and `python validate_rebranding.py`, then build/start the stack
   yourself. Check PostgreSQL/Flyway readiness, authenticated technical routes,
   internal User lookup, and telemetry after startup. The optional database test
   can run with `HOSPITAL_DATABASE_TESTS=true` and real service configuration.

Introduce future Hospital features through reviewed API contracts, authorization
rules and real PostgreSQL migrations. No patient/doctor/appointment/medical/billing
features are part of this foundation.
