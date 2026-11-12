# Phase6A remediation verification — 2026-11-12

## A. Executive summary

**Compressed-rollover cause: remediated, deployed and verified for ordinary downtime within retained-file capacity. Telemetry production security: partially implemented as an inactive candidate; live failure remains OPEN. Overall production readiness cannot be claimed.**

The three applications now write bounded, uncompressed, immutable-name JSON spool files. Fluent Bit discovers these files using its original persistent tail databases, while continuing to drain legacy active logs. A real Logback/Fluent Bit isolated fixture verified normal rotation, collector downtime, recovery, restart and duplicate observations against two protocol sinks. Fresh real-stack regression verified Loki and OpenSearch delivery separately. No production lossless or exactly-once claim is made.

Native TLS/mTLS and OpenSearch role/security configuration are prepared separately, without enabling security on existing volumes or inventing credentials. No authorized PKI, bootstrap hashes or isolated security migration evidence was available. Existing loopback-only development access remains unchanged.

## B. Baseline and evidence

The immutable pre-change baseline is the ignored local artifact `phase6-evidence/remediation/phase6-20261112T032932Z-de75a086/baseline.json`; `phase6a-remediation-state.log` identifies it. Original Phase6A reports and `phase6-measurements.json` remain historical evidence (750PASS,2FAIL,10NOT VERIFIED,2NOT APPLICABLE). This report is a follow-up, not a rewritten historical assessment.

- Target `springboot_project`:18 containers; unrelated `jp_dev`:16 containers. Baseline93 Docker volumes.
- All protected database/observability volume identities, existing data,12 protected environment/key fingerprints, Grafana resources and JWKS bodies captured before rollout.
- Grafana12.2.0, Prometheus3.13.5, Fluent Bit3.2.10, Loki3.5.8, OpenSearch3.9.0, Collector0.143.0, Tempo2.9.0.
- All repositories remained on `develop` with unchanged HEADs. Pre-existing Phase6A documentation/tooling was uncommitted and preserved. Module worktrees were clean before remediation; deliberate changes are listed below.
- Existing APIs were launched base-only; Fluent Bit had the existing debug override. Rollout preserved those per-service Compose choices instead of accidentally adding debug publications to applications.

## C–F. Telemetry security, OpenSearch and TLS

See [actual endpoint inventory and threat assessment](telemetry-security.md), [socket evidence](remediation-endpoints.json), and [complete secure-candidate procedure](secure-production/README.md).

Actual failure: Grafana authenticates users and public-port Actuator access is restricted, but the shared bridge carries plaintext unauthenticated telemetry. OpenSearch has its security plugin disabled. All existing host publications already bind loopback; no wildcard publication was found to remove. No additional live exposure was introduced and no working development port was removed merely to appear to remediate this issue.

The candidate uses native TLS/mTLS on Fluent Bit→Loki/OpenSearch, APIs→Collector, Collector→Tempo, Prometheus scraping/web and Grafana→datasources. OpenSearch adds native transport/HTTP TLS, required client certificates, separate health/writer roles, non-demo credentials and manual security-index initialization. Grafana preserves login authentication and gains HTTPS/metrics authentication. Five small per-component metrics proxies are necessary because the current application/Fluent Bit/Collector metrics listeners lack appropriate native TLS. Plaintext upstream sockets become loopback-only within shared service network namespaces. Single-tenant backend APIs still trust CA-authorized clients broadly; this is not a multi-tenant authorization design.

Optional application metrics bind-address support was implemented and tested in all three modules. **It is not in the reused running images.** Secure activation requires new images; merely setting its environment variable on old images would leave the original bridge metrics listener exposed. Development default remains `0.0.0.0`, preserving existing Prometheus behavior.

No live OpenSearch migration was attempted. Existing indices/ISM policies need authenticated operational tooling, complete security configuration, an approved backup and isolated restore/migration validation. Fluent Bit's index-create/bulk permissions, Dashboards server credentials, health client identity, certificate SAN/DN/EKU requirements, startup bootstrap ordering, rollback and negative access tests are documented. No Grafana OpenSearch datasource currently exists. Candidate structural validation passed; native secure startup/handshakes/access rejection remain NOT VERIFIED. Never apply the examples directly to existing live volumes.

## G–H. Rotation root cause and implementation

Previously, Logback renamed the fixed active file into an immediately compressed `.gz` archive. Fluent Bit tailed only the active `.log`. During collector downtime an unread inode could be compressed/removed before rediscovery, so retention of the gzip archive did not make its events readable by the tail input.

An initially investigated active-plus-renamed-archive glob was rejected: native Fluent Bit3.2.10 removes rotated-file tracking/checkpoints after rotation handling, and isolated restart tests observed replay. The final design avoids rename entirely: Logback's `RollingFileAppender` has **no fixed `<file>`**; its size/time policy opens a new immutable path `${LOG_DIR}/spool/${APP_NAME}.%d{yyyy-MM-dd}.%i.log`. It closes the previous file without renaming/compressing it. Fluent Bit discovers each stable filename once and retains its offset in the existing service DB. No delayed-compression job or acknowledgement-unaware compressor is introduced.

Defaults remain100MB per file,30-day history and2GB total archive cap per application. New variables allow explicit sizing; cleanup is asynchronous and an active-file/cleanup allowance must be budgeted. Uncompressed storage costs more than gzip. Capacity must cover expected log rate × tolerated collector outage plus headroom. Both age and size policies can delete unread data if this budget is exceeded. That remains a documented durability limit, not a claim of indefinite losslessness.

Fluent Bit tails the legacy active path plus each service's `spool/*.log`; existing gzip archives are excluded and untouched. DB locations, full sync/WAL, filesystem buffering, output queue limits and retry settings remain unchanged. `DB.compare_filename Off` retains inode-based compatibility. Legacy fixed files remain for safe drainage; they are not reset/truncated. Existing old gzip archives require a separately reviewed deduplicating backfill if historical gaps must be recovered; no backfill was executed.

## I. Delivery guarantees and reliability evidence

1. Application encoding and append create JSON in the mounted log volume; this is not proof of fsync per event or crash durability.
2. Stable files remain discoverable until retention/cap cleanup. Fluent Bit stores offsets in persistent databases and chunks in persistent output buffering; discovery/offset/buffer stages have distinct failure windows.
3. Each output has independent queues/retries. OpenSearch `Generate_ID On` helps retry identity within its processing scope; it does not guarantee global deduplication across rereads. Loki delivery also can duplicate after acknowledgement ambiguity.
4. Backends acknowledge writes separately. Source creation, offset persistence and dual-backend acknowledgement are not one transaction. Practical operation targets recoverable at-least-once delivery **within capacity and documented failure assumptions**, with possible duplicates; exactly-once and crash/overflow guarantees are not established.

Fixture run `330e0d2be9` passed12 checks with52 synthetic events observed once per sink and72,688 source bytes. It used actual Logback1.5.38 and Fluent Bit3.2.10, a new internal network/volume, and native Loki-push/OpenSearch-bulk protocol outputs to isolated acknowledgement sinks. Tests covered legacy DB reuse, existing unread uncompressed files, live size rollover, downtime across multiple rollovers, restart, preserved JSON trace fields, gzip exclusion and bounded fixture storage. **These sinks are not actual Loki/OpenSearch storage.** Fresh live-stack tests separately proved real storage ingestion. Only fixture collectors were stopped for downtime testing; the live collector was restarted solely to apply configuration.

The fixture retains stopped task-owned containers and its volume/network for evidence. Failed earlier experimental fixtures were also retained; they never mounted live logs or databases. No destructive cleanup was performed.

## J–K. Deployment and automated tests

The logging-only rollout mounts the version-controlled Logback file read-only at `/etc/application/logback-spring.xml`, sets `LOGGING_CONFIG`, and reuses existing application images. It gracefully restarted live Fluent Bit once and sequentially recreated only User, Learning and JWKS with `--no-deps --no-build --pull never`, waiting for readiness after each. No database/backend/Grafana container was recreated. Public ports, network connectivity, JWT behavior and10% sampling were preserved. The deployment check initially hit a helper URL bug after successful rollout; that helper was corrected and the independent preservation check passed. No second deployment was needed.

| Command | Exact result / scope |
|---|---|
| `./mvnw.cmd -o test` from `springboot-user-api` |105 tests,0failure/error/skipped; BUILD SUCCESS |
| Same from `springboot-learning-api` |121 tests,0failure/error/skipped; BUILD SUCCESS |
| Same from `springboot-jwks-api` |83 tests,0failure/error/skipped; BUILD SUCCESS |
| `python -m unittest discover -s observability -p test_remediation_contract.py -v` |8 tests PASS; offline configuration contracts |
| `python -m unittest discover -s observability -p test*.py -v` |15 tests PASS;7 original tooling tests plus8 new contracts |
| `python observability/test-rotation-remediation.py` |12 checks PASS;52 events per isolated sink |
| `python observability/validate-secure-candidate.py --structure` |PASS, exit0; no containers started; runtime security NOT VERIFIED |
| `python observability/validate-secure-candidate.py` |NOT VERIFIED, exit2;10 missing authorized prerequisite variables; no activation |
| `python observability/verify-remediation.py` |795PASS,1FAIL,11NOT VERIFIED,2NOT APPLICABLE; exit1 correctly reports remaining production-security failure |
| `python observability/remediation-runtime.py verify` |PASS; original volume/data/Grafana/key/container preservation |

Maven total:309 tests (including9 new bind-address cases). Existing meaningful JWKS file-appender assertions now verify immutable spool/no fixed file; tests were not skipped. Early fixture experiments and a legacy gzip expectation failed during development and were corrected. A lazy internal-client meter scrape race in the first regression was addressed by bounded waiting for the real series, without inventing or replacing it. Final results above supersede those unsuccessful attempts while retaining their ignored logs locally.

Final fresh runtime evidence: `phase6-evidence/remediation-regression/phase6-20261112T040753Z-36ca4221/results.json`. Native Prometheus configuration/rule, Collector, Loki, Tempo and Fluent Bit validators run against installed images through the reused Phase6 tooling. They validate **live development configuration**, not unstarted secure templates. Eight dashboards/174 panel queries,21 alert rules, nine scrape targets and five recording rules were verified. All three APIs were ready; real login/access/refresh/logout, expected unauthorized/forbidden behavior, JWKS bodies/issuers/key compatibility and Learning→User internal JWT communication passed with existing ignored credentials. Positive administrative account access remains NOT VERIFIED because that account lacks the role.

Fifteen source HTTP events were matched across live Loki/OpenSearch with numeric status/duration, JSON/correlation/trace fields and redaction checks. A sampled Learning→User trace verified propagation, parent-child relationships and Tempo/Grafana API resolution; sampling was not changed. Grafana login, datasource connectivity, rule health and delivery mute remained intact. Browser rendering/navigation and elapsed alert lifecycle remain NOT VERIFIED; no external notification was sent.

The final11 NOT VERIFIED items are: positive admin access; browser behavior; real elapsed alert lifecycle; external notifications; crash/overflow durability; physical retention deletion; backup/restore; production load capacity; production async endpoints; backend disk-pressure alerts; broad lossless collection. The latter remains broader than the specific compression cause now verified fixed. Original queue, retention and restart evidence is preserved without upgrading it to crash or expiry proof.

## L–M. Persistence and variables

Final preservation compared the original baseline, not merely post-change state: all93 original volumes remained; database mounts and every unrelated container ID/start time remained unchanged. Protected environment/key fingerprints, JWKS responses, Grafana dashboards/alerts/contact points/policies/datasources, OpenSearch index UUIDs/nondecreasing counts, pre-remediation Loki records, timestamped historical Prometheus samples and old Tempo traces passed. New fixture volumes/networks are additive and intentionally retained. No existing log file was deleted or overwritten by the test tooling; normal configured retention remains active.

| New variable | Default / requirement | Development / production |
|---|---|---|
| `APP_LOG_MAX_FILE_SIZE` | Optional,`100MB` | Size rollover; tune to log rate and storage budget |
| `APP_LOG_MAX_HISTORY` | Optional,`30` | Days retained; does not protect unread files from size cleanup |
| `APP_LOG_TOTAL_SIZE_CAP` | Optional,`2GB` | Per-app policy budget, plus active/cleanup allowance; uncompressed bytes |
| `APP_METRICS_LISTENER_ADDRESS` | Optional,`0.0.0.0` | Unchanged development bridge scraping; secure candidate requires`127.0.0.1` and rebuilt image |

Root/per-service/module examples document these values. Actual `.env` values were not overwritten. Ten secure-only required variables and secret/PKI ownership requirements are documented in the [candidate README](secure-production/README.md); no credential has a default.

## N–O. Updated acceptance and remaining work

| Criterion | Follow-up status |
|---|---|
| Endpoint exposure inventory |PASS |
| Unnecessary external host exposure |PASS: none found; existing loopback-only access preserved |
| Development access and telemetry continuity |PASS |
| Secure production configuration and migration procedure |IMPLEMENTED BUT NOT DEPLOYED; structural checks PASS |
| Live native auth/TLS/OpenSearch role enforcement |NOT VERIFIED / BLOCKED; original security FAIL remains OPEN |
| Compression root cause / compatible implementation |PASS, deployed |
| Real rotation + isolated downtime/restart + offset reuse |PASS within retained-file budget |
| JSON schema, dual-store live delivery |PASS |
| Duplicate-free fixture observation |PASS for52/sink only; global exactly-once NOT CLAIMED |
| Bounded policy configuration |PASS; cleanup/retention capacity can still evict unread files |
| Crash durability, saturation, physical expiry, restore, load |NOT VERIFIED; Phase6B approval gate retained |
| External notification |NOT VERIFIED; existing mute retained |
| Original volumes/keys/contracts/unrelated containers |PASS |

No Phase6B destructive/external test was executed. [Phase6B plan](phase6b-validation-plan.md) still gates crash, exhaustion, physical retention, restore, notifications and representative load. The authorized isolated ordinary rotation test belongs to this remediation, not an implicit approval for those tests. Secure migration also requires a separately approved isolated clone and credentials before any live activation.

## P–Q. Cross-project and Git impact

`japanese-learning` was not modified; it requires no implementation prompt or changes. JWKS endpoints, public key bytes, IDs, issuers, signing/decoding/authentication code and API contracts are unchanged. Sequential JWKS logging restart was verified ready; existing consumers retain the same host/network routes.

Root changes: Compose logging mounts/env; root environment examples; Fluent Bit input discovery; remediation scripts/fixture/security candidate, security inventory and follow-up docs. Existing Phase6A untracked documentation/scripts and `.gitignore` modifications remain present. New `test_remediation_contract.py` adds offline checks. All module changes: environment examples, Logback policy, optional metrics bind property and three-case bind test. JWKS additionally updates its existing logging configuration test. No business/database/JWT files changed. Root Git reports dirty submodule worktrees intentionally; no submodule commit pointers changed.

No commits, pushes, branch switches, resets, volume deletion, key regeneration, database record modification or unrelated-container restart occurred. Runtime auth tests touched only their own temporary test session under the existing authorized account.

## R. Recommendation

Accept the bounded immutable-spool remediation for development/ordinary collector downtime, with explicit sizing and recovery monitoring. Review the secure-production candidate separately and supply approved PKI/credentials before isolated native validation and a coordinated migration. Both original failures cannot be declared fully resolved: security remains open, and general data durability/recovery/capacity evidence remains incomplete.
