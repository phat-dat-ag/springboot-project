# Phase 6A verification — 2026-11-12

## A. Executive summary

**Phase6A implemented and executed. Phase6B prepared only; NOT EXECUTED. Overall
production readiness cannot be claimed.** The final comprehensive assessment
recorded **750 PASS, 2 FAIL, 10 NOT VERIFIED, 2 NOT APPLICABLE**, returning exit1
intentionally for confirmed readiness failures. It exercised actual telemetry and
Grafana, not just JSON syntax. All300 Java tests and seven Python safety tests passed
without failures, errors or skips. No existing service was restarted/recreated,
no runtime configuration changed and no external notification was sent.

Two confirmed failures: the current deployment lacks production telemetry
authentication/TLS/isolation beyond its trusted development network, and immediate
compressed rollover can strand unread source logs while Fluent Bit is stopped.
Critical unverified gates include external delivery, crash/overflow durability,
physical retention deletion, restores and representative capacity.

New tooling: `verify-phase6.py`, `summarize-phase6.py`, `test_phase6_tooling.py`.
New operator/readiness/backup/capacity/incident runbooks and a separate approval-gated
test plan are linked from README. No Java/application/provisioning changes.

Final immutable run baseline and local detailed results:
`observability/phase6-evidence/phase6-20261112T031510Z-c66c0468/`.
Final result UTC03:15:30. Sanitized publishable evidence:
[phase6-measurements.json](phase6-measurements.json) and
[phase6-checklist.md](phase6-checklist.md). Local raw evidence is ignored; no test
JWTs, passwords or private keys are persisted by the new verifier.

## B. Baseline and environment

Read base/debug Compose, all service POMs and relevant security/logging/test source,
submodule AGENTS instructions, existing verifiers, provisioning and infrastructure
configs, environment examples/effective values in memory and Phase0–5 reports.
The consolidated checklist transcribes historical PASS/FAIL/NOT VERIFIED rows,
including superseded claims, and separately lists current executed results.
Prior passes were not assumed to remain true.

| Component | Inspected running/configured version |
| --- | --- |
| Grafana / Prometheus |12.2.0 /3.13.5, confirmed APIs and native tools |
| Fluent Bit / Loki |3.2.10 /3.5.8 |
| OpenSearch / OpenSearch Dashboards |3.9.0 /3.9.0 |
| Collector Contrib / Tempo |0.143.0 /2.9.0 |
| MySQL / PostgreSQL |8.4 pinned digest /17.6 |
| Spring Boot User / Learning / JWKS |4.1.1 /4.1.2 /4.1.2 from POMs |
| Local Maven Java |Temurin17.0.19 |

Captured all34 containers, including23 running at the observed baseline,
18 target-project containers and16 unrelated `jp_dev` containers, plus93 volumes.
Snapshots include IDs/start times/restart counts, image IDs, read-only mounts,
network/ports/resource/log limits, actual database/observability volume identities,
twelve protected env/key/credential fingerprints, existing Grafana dashboard/rule/
datasource/contact/policy identities or hashes, Prometheus targets, backend data
availability and Git state. No secret-bearing Compose dump is stored or printed.

Initial shell inspection showed the prior feature branch; between that inspection
and the first immutable runtime baseline, root was externally on `develop` at
`ed8b88148ead44f01eb13766d6c6c1a1be0ac5b0`. Every immutable Phase6 baseline and
preservation check records that same root branch/HEAD. No branch-changing command
was issued by this work, and it did not attempt to undo the observed movement.
Root was clean at initial inspection. Submodule worktrees remained clean.

## C. End-to-end observability

All three API readiness endpoints returned UP. Bounded synthetic requests used
unique correlation IDs or verified generated UUIDs and unique sampled W3C parents.
Root sampling remained0.1; deterministic sampled remote parents did not alter the
deployment probability. The final run verified15 per-service completion records
through application→Fluent Bit→Loki/OpenSearch and application→Collector→Tempo.

PASS: canonical service/environment/version, numeric final status/duration,
independent correlation/trace IDs, distinct request contexts, actual stored spans,
safe metric labels and corresponding source identities in both log destinations.
One completion per matching probe was observed in each store; no exactly-once
delivery guarantee is inferred. Existing telemetry IDs remain JSON/trace context,
not user-specific metric or Loki stream labels.

## D. Authentication and JWT/JWKS

The existing ignored local credentials were used only in memory. PASS: login,
authenticated Learning `/me`, access-token verification through a protected API,
refresh rotation, new-token access and logout of this test's own session. No user
account/password/role or unrelated session was changed; no direct SQL was issued.
These authorized auth endpoints necessarily create/rotate/remove their own session
records, unlike prohibited business-data/database mutations.

PASS: Learning→User internal JWT request returned the existing subject, external
access token was rejected on User's internal route with401, invalid bearer was401,
unauthenticated calls were401, and an authenticated public metrics request was403.
The available account is non-admin: `/admin/users/{id}` correctly returned403.
Positive administrative User access is NOT VERIFIED without suitable credentials;
positive User access via the real authenticated internal client passed.

PASS: public User/Learning JWKS responses remain identical to baseline hashes;
access-token `kid` matches a published RSA key, algorithmRS256 and configured issuer
match. Maven tests also exercise wrong issuer/audience/subject/signature/kid/type
and external/internal token boundaries; this does not claim every negative case
was independently re-signed and sent to the deployed APIs. No key was regenerated.

## E. Structured logging

For each verified completion, checked timestamp parsing/timezone, level, canonical
service/environment, nonempty version, event, correlation/trace/span, HTTP method,
bounded route, integer status, finite nonnegative numeric duration, outcome and
error category. Both stores contained matching values for the same source identity.
Independent probe IDs verified no live cross-request context reuse. Actual tested
credentials, token values and identity values were absent from inspected matching
logs/spans and live metric exposition; forbidden sensitive span attribute names
and metric label keys were absent. No response bodies or credentials were printed.

Optional fields/MDC cleanup/async behavior are covered by the unchanged isolated
encoder/filter/servlet/tracing Maven tests, all executed successfully. Live async
endpoint behavior remains NOT VERIFIED because no public production async fixture
exists; no diagnostic endpoint was added. The inspected-telemetry window is not
a universal proof against every future sensitive input.

## F. Metrics and Prometheus

**9/9 targets UP, no scrape errors:** three applications and Prometheus, Loki,
Collector, Tempo, Fluent Bit and Grafana. Actual HTTP count/buckets, JVM heap/GC/
threads/CPU, security counters, User/Learning Hikari active/pending/max/acquisition/
timeouts, managed internal HTTP client metrics and Collector/Fluent Bit counters
were queried. All3 services had finite p50/p95/p99 from the real histogram buckets.
JWKS has no Hikari pool, correctly classified NOT APPLICABLE.

Five recording rules remain loaded/healthy. Native promtool checks passed using
the exact installed image ID; five synthetic rule scenarios/eleven expression
assertions cover normal traffic, absent errors, idle traffic, missing telemetry and
known histogram/error values. No live scrape was stopped to force missing data.
Rates precede aggregation and percentile calculations preserve `le` boundaries.
Unknown/zero maxima and idle error ratios are not turned into misleading values.

## G. Distributed tracing

Final authenticated linked trace: `152e8ba9676e424eaf5663d30265f676`.
The stored Learning SERVER, managed CLIENT and User SERVER span chain had the
correct parent relationships, positive timings and correct resource identity/
environment. Each server's real span ID matched its log record. Correlation was
independent from trace ID and matched across Learning/User completions.

PASS: Tempo trace-by-ID through Grafana's proxy, three actual TraceQL exploration
forms, log-derived trace extraction, trace resolution and reverse trace-ID Loki
query. Traces for the other direct probes also stored/queried correctly. No second
metrics pipeline, service graph or span-derived metric assumption was introduced.
Browser waterfall/click behavior remains NOT VERIFIED separately from API paths.

## H. Grafana dashboards

All8 expected stable `sb5-*` dashboards exist, are file-provisioned and belong to
folder UID `observability`. Each dashboard's variables, time range and30s refresh
match source. Field options, units, legends and no-data configuration match source;
datasource UIDs resolve. Executed174 real queries: every Phase5 panel target with
all-service selection and with Learning/environment filtering. Filtered output
service labels were checked when present. Empty/NaN results are permitted only as
data states, not parser failures. No parser/datasource error occurred.

The original ninth application-log dashboard remains unchanged. API tests do not
prove browser rendering, variable interpolation in encoded Explore links, heatmap
appearance or actual click behavior; those remain NOT VERIFIED. No browser tool
was available and no dependency/browser was installed to bypass that limitation.
See [dashboard inventory](dashboard-inventory.md) for every purpose/panel/variable.

## I. Grafana alerting and notification readiness

All21 unique rules loaded and evaluated with `health=ok`; final states inactive.
Compared exact source query semantics, threshold conditions, labels, pending,
no-data/error modes and keep-firing configuration. Grafana adds benign query-model
defaults and omits recovery fields in its ordinary provisioning response; the
authoritative export API verified `keepFiringFor: 1m`. Source comparison accounts
for those representation differences, not threshold drift.

PASS: safe non-persisted normal0, breach1, no-data empty and execution-error preview
evaluations. Actual elapsed Normal→Pending→Firing→Resolved remains NOT VERIFIED;
the sole persistent Grafana instance was not modified with synthetic timed rules.
Phase6B G1 specifies a disposable clone for that experiment.

PASS: all-day `phase5-delivery-disabled` mute loaded and referenced by every rule;
grouping service/environment/severity, wait1m, grouping5m, repeat4h unchanged.
Existing contact/policy/rule hashes match the fresh baseline. Inactive environment-
driven webhook examples are documented and remain inactive. Actual external and
recovery delivery remain NOT VERIFIED. No live rule was unmuted, no transport was
enabled and no external message was sent. Exact future authorization prerequisites
are in [Phase6B E1](phase6b-validation-plan.md) and [alerting.md](alerting.md).

## J. Pipeline reliability

Native pinned-image validation passed for Collector, Fluent Bit and Loki; native
Prometheus config/rules tests passed. Tempo's loaded `/status/config`, readiness
and actual trace queries verified its current config; no unsupported standalone
Tempo validation flag is claimed. Native fixtures used no network, no live data
volumes, bounded memory/CPU/PIDs/tmpfs and `--pull never`; no dependency installation.

PASS: current persistent tail DB/WAL/full-sync/checksummed FS buffer contract,
per-output budgets and retry configuration, Collector persistent byte queue/fsync/
retry contract, named storage mounts and fresh data delivery. Fluent Bit current
process had zero permanently failed retries/dropped records. Queue utilization0
and Hikari pending0 were observed; this is not proof of saturation behavior.

Phase4 ordinary outage/restart and isolated tail tests remain historical evidence;
they were not repeated against live backends and do not prove crash durability.
The compressed-rotation gap is a confirmed architecture/configuration failure for
lossless unread-history collection. A concrete uncompressed archive tail/delayed-
compression/watermark strategy is documented, not deployed: matching, retention,
inode/duplicate behavior and storage impact require isolated validation first.
No unsafe archive replay or overlapping tail input was added.

## K. Storage, retention and resource observations

All93 existing volumes and current DB/observability mount identities are preserved.

| Store | Configured / active evidence | Deletion evidence |
| --- | --- | --- |
| Loki |30d, TSDB/filesystem, compactor retention enabled/delete delay2h, config accepted | Expiration execution/physical removal NOT VERIFIED |
| OpenSearch |30d lifecycle;6 dated indices assigned and enabled; hot transition checks show condition_not_met without failure | Actual delete action/physical deletion NOT VERIFIED |
| Tempo |72h in loaded config, persistent WAL/blocks | Actual expired block/trace removal NOT VERIFIED |
| Prometheus |Active15d/2GiB flags, persisted TSDB and healthy rules | Time/size enforcement/physical deletion NOT VERIFIED |
| Source/Docker logs |100MB/30d/2GB per-app archives inspected; effective10m/3 Docker rotation on11 services | No forced rollover or deletion demonstration |

Three legacy OpenSearch app indices remain unmanaged, an ongoing growth risk.
Collector queue64MiB payload, FB nominal64M+3×32M logical outputs remain unchanged;
neither is a filesystem quota. Current readiness checks do not measure hard
overflow, inode exhaustion, crash recovery or maximum outage coverage.

Final bounded sample: OpenSearch1.004GiB/2GiB RSS, heap60%; API heaps roughly
User21.7%, Learning21.3%, JWKS15.8%; Hikari utilization/pending0; Collector queue0.
OpenSearch node filesystem available955,883,905,024 bytes. This is not a host-wide
capacity guarantee or implemented pressure alert. Actual174 query samples were
2.43–40.45ms, median6.19ms locally. See [capacity-planning.md](capacity-planning.md)
for all13 running target-container samples and budget calculations. No production
RPS, concurrency, storage-growth envelope or representative load capacity is claimed.

## L. Backup and restore

No registered OpenSearch snapshot repository; Prometheus admin API disabled.
Git reconstructs provisioned config but not users, personal dashboards, TSDB/log/
trace history, secret encryption state, queues or coherent tail/source state.
No verified external backup schedule or established RPO/RTO was found in this repo;
external organizational facilities were not assessed.

[backup-restore.md](backup-restore.md) lists component-native mechanisms,
consistency requirements, protected credentials, restore ordering, encryption,
manifests, checksums and exact isolation prerequisites. No live hot-directory copy
is presented as a verified backup. No destructive restore or disposable restore
rehearsal was executed; restore success/integrity/timing remain NOT VERIFIED and
are explicitly planned under Phase6B D1/D2.

## M. Security and privacy

PASS: current loopback port bindings, unpublished Collector/Tempo/Fluent Bit
endpoints, read-only key mounts, denied public metrics paths including with a
valid token, protected sensitive Actuator paths and Grafana API authentication.
Twelve protected env/key/credential fingerprints remained unchanged. Live matching
telemetry and exposition did not contain tested credentials/tokens/identity or
prohibited sensitive dimensions. No keys, tokens, contact destinations or private
Compose environment values are printed in the new verifier's output.

**FAIL for production access-control readiness:** disabled OpenSearch security and
trusted plaintext backend network. These are existing local-development choices;
Phase6A did not weaken them or silently introduce a new deployment/auth contract.
Hardening needs a separately reviewed topology/TLS/authentication rollout, not a
test that merely exposes more endpoints to obtain successful probes.

## N. Automated tests and commands

| Command | Exact final result |
| --- | --- |
| `python observability/verify-phase6.py` | exit1 by readiness design:750 PASS,2 FAIL,10 NOT VERIFIED,2 NOT APPLICABLE; no unexpected verifier failures in final run |
| `python observability/summarize-phase6.py` | exit0; sanitized current/historical checklist and measured JSON |
| `python -m unittest discover -s observability -p test_phase6_tooling.py -v` |7 tests passed,0 failures/errors |
| `.\mvnw.cmd -o test` in User |102 tests,0 failures/errors/skips; exit0 |
| `.\mvnw.cmd -o test` in Learning |118 tests,0 failures/errors/skips; exit0 |
| `.\mvnw.cmd -o test` in JWKS |80 tests,0 failures/errors/skips; exit0 |
| `python -m py_compile observability/verify-phase6.py observability/summarize-phase6.py` | exit0 |
| `git diff --check` | exit0 |

Maven initially could not acquire `.m2` lock files inside the sandbox. The same
offline suites were rerun outside the sandbox with permission, using existing
dependencies; all passed. Surefire XML totals were independently summed:
User16 report files, Learning17, JWKS13. New Python tests check secret-safe error
output, bounded subprocess timeout, deterministic hashing, secret-excluding and
mount-order-normalized inventories, truthful FAIL/NOT VERIFIED reporting and
configuration-derived access/rotation findings. Both current findings were also
rechecked directly against current files; they are not unconditional hardcoded FAILs.

During new-tool development, initial attempts found numeric/null role handling,
Loki stream-versus-metric response shapes, Docker mount ordering and Grafana
normalized/exported fields. They were corrected, not hidden as application
successes. Python test discovery initially matched no hyphenated test module;
the file was renamed to a valid module and the final seven tests were actually executed.
Native Fluent Bit fixture mounts now exactly match the real renamed parser file.
Historical failed/partial local runs remain separate from the final evidence.

The verifier fixes project identity; supports repeated Compose files and loopback
endpoint overrides, configurable existing ignored credentials and1–30s HTTP
timeouts,60s subprocess limits and45s bounded delivery polling. It creates a new
ignored baseline/run each time and compares existing state afterward. It never
deploys/restarts services, installs packages, sends notifications or executes direct
database mutations. Exit0/1/2 have documented CI meaning. Known readiness failures
are deliberately not suppressed into a green production gate.

## O. Production readiness matrix

| Criterion | Result | Scope |
| --- | --- | --- |
| Development observability | PASS | Actual logs/metrics/traces and300 Java tests |
| Operational monitoring | PASS | Current APIs/queries/health work; storage/browser gaps remain separate |
| Internal alert evaluation | PASS |21 rules healthy, config/export and previews verified |
| External incident notification | NOT VERIFIED | No authorized destination send; all-day mute retained |
| Data durability | FAIL | Confirmed unread compressed-archive gap; crash/overflow also unverified |
| Backup/recovery | NOT VERIFIED | No restore rehearsal or measured RPO/RTO |
| Production capacity | NOT VERIFIED | Bounded development measurements only |
| Overall production readiness | FAIL | Production access/loss gaps plus critical unverified gates |
| Runtime metric/auth protection | PASS | Public metrics forbidden, private endpoints internal, Grafana authenticated |
| Production backend access controls | FAIL | Current trust-only/plaintext architecture |
| Login/refresh/logout/internal JWT/JWKS | PASS | Current existing-account flow and isolated negative tests |
| Positive administrative User access | NOT VERIFIED | Available credentials non-admin; expected403 passed |
| JSON schema/dual-store identity/no observed duplicates | PASS |15 final matching completions; not exactly-once proof |
| Runtime async endpoint | NOT VERIFIED | Isolated Maven async/MDC coverage passed |
|9 target health and5 recording rules | PASS | Real Prometheus and native fixture tests |
|8 Grafana dashboards/API filters | PASS |174 all/filtered queries; source units/legends/options matched |
| Browser rendering/click navigation | NOT VERIFIED | No browser automation available |
|21 alert definitions/mutes/current evaluation | PASS | Authoritative exports and no policy/contact drift |
| Elapsed pending/firing/resolved lifecycle | NOT VERIFIED | Planned isolated clone G1 |
| Persistent queue/buffer configuration and fresh delivery | PASS | Current native validation/mounts/metrics/probes |
| Hard crash/overflow/disk-full recovery | NOT VERIFIED | Phase6B only |
| Retention config/ISM assignment and evaluation | PASS | Actual flags/config/enabled hot-state observations |
| Physical retention deletion | NOT VERIFIED | No expiry/deletion forced or observed |
| Backend disk-pressure alerting | NOT VERIFIED | Reliable collected source not implemented |
| JWKS database pools | NOT APPLICABLE | No datasource |
| Tempo service graphs/span metrics | NOT APPLICABLE | Not enabled/required |
| Container/volume/key/branch preservation | PASS | Fresh baseline comparison; see branch timeline caveat above |

Every individual executed check and explicit gap is preserved in the consolidated
checklist; table-level readiness is not obtained by counting green health checks.

## P. Phase6B plan

[phase6b-validation-plan.md](phase6b-validation-plan.md) specifies individual
approval gates for Fluent Bit overflow, Collector saturation, backend disk-full,
compressed rotation mitigation, Collector/FB/backend hard crashes, natural Loki/
OpenSearch/Tempo/Prometheus retention, consistent backups/disposable restores,
authorized external notification grouping/repeat/recovery/mute, representative
performance and an isolated timed alert lifecycle.

Each test states objective, prerequisites, exact manifest-scoped components,
isolation, risks, precautions, steps, expected results, evidence, rollback and
explicit approval. A dedicated host is preferred for resource/failure tests to
avoid affecting shared `jp_dev`. No host-wide disk fill, live-volume restore,
timestamp manipulation, uncontrolled load, live-rule threshold change or automatic
external delivery is authorized. **None of Phase6B was executed.**

## Q. Cross-project compatibility

No JWKS endpoint, key format/kid, issuer, signing/validation behavior, internal auth,
network contract or response changed. Public response hashes and real internal
communication passed. `japanese-learning` requires no changes; no separate Codex
implementation prompt is necessary. It was not edited and all16 `jp_dev` container
identities/start times/mounts remained intact.

## R. Git and container preservation

Changed/new root files: `.gitignore` evidence exclusion; observability README and
logging-pipeline links; verifier, summarizer, seven-test safety module, generated
sanitized checklist/measurements and the requested verification/readiness/
operations/incident/backup/capacity docs plus separate Phase6B plan. No deployment,
dashboard, alert, datasource, Collector, Fluent Bit or application config changed.

| Repository | Preserved runtime-baseline branch / HEAD | Worktree outcome |
| --- | --- | --- |
| Root |develop /`ed8b88148ead44f01eb13766d6c6c1a1be0ac5b0` | Only Phase6 tooling/docs changes; no commit/push |
| User |develop /`e7991b34d310b94696469dda30c108645e06d00e` | clean |
| Learning |develop /`f6a61f6a0d1284adc831fa6f04b83ce23c02faa2` | clean |
| JWKS |develop /`7879d155eddb45fb079800709f49a3c3a1566120` | clean |

All34 original container IDs, start times, restart counts, ports, networks and
mounts match the final fresh baseline; no live restart/recreation. All93 volume
names remain, with no new persistent volumes. All twelve protected fingerprints,
effective Compose digest and deployed config hashes match. Grafana contact/policy/
rule/datasource/dashboard hashes and JWKS bodies remain unchanged. Only temporary
network-disabled native validation fixtures were started with `--rm`; no existing
container/volume cleanup command was used. No RSA regeneration or account changes.

## S. Final recommendation

Accept Phase6A as completed evidence-based validation and operational documentation
for the current development deployment, with explicit failed/unverified production
gates. Operational queries and internal evaluation work, but muted/unverified
external delivery cannot support a production paging claim. Do not claim lossless
or crash-durable delivery, verified backup recovery, physical retention deletion
or representative production capacity. Review and separately authorize selected
Phase6B tests and any production-hardening changes before changing those statuses.
Stop for review. No commit or push.

## 2026-11-12 remediation follow-up (historical assessment preserved)

See [Phase6A remediation report](phase6a-remediation.md) and [telemetry security inventory](telemetry-security.md). Original measurements above and `phase6-measurements.json` are not replaced.

The compression-specific failure is now **PASS within retained-file capacity**: immutable-name uncompressed bounded spool files and archive-aware Fluent Bit discovery were deployed. Twelve isolated checks recovered52 retained events once per protocol sink across rotation/downtime/restart; actual Loki/OpenSearch delivery was independently regression-tested. Broad lossless/crash/overflow guarantees remain NOT VERIFIED.

Production telemetry security remains **FAIL / OPEN** in the running stack. A fail-closed secure deployment candidate and native OpenSearch migration procedure are implemented but **NOT DEPLOYED**; only structural checks passed. No authorized production PKI/credential bootstrap or isolated security migration was available.

Fresh regression `phase6-20261112T040753Z-36ca4221`:795PASS,1FAIL,11NOT VERIFIED,2NOT APPLICABLE; exit1 appropriately retains the security failure. All309 Maven tests passed. Nine targets, five rules, eight dashboards/174 queries,21 muted alert rules,15 dual-store events and linked service tracing passed. Existing volume/data/Grafana/key/unrelated-container preservation passed. Only three APIs and Fluent Bit changed for logging activation. No Phase6B test, external notification, commit or push was performed. See the linked report for exact commands, limitations and acceptance matrix.
