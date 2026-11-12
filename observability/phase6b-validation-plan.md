# Phase 6B — separate approval-gated validation plan

**PREPARED ONLY. NOTHING IN THIS PLAN WAS EXECUTED.** Completing Phase6A does not
authorize any test below. Each test needs separate approval naming its target
manifest, resource ceiling, duration, data/destination owners and rollback. No
live application thresholds, notification mutes, source logs, keys, databases or
backend volumes may be changed to force a result.

## Mandatory isolation and approval manifest

Prefer a dedicated disposable Docker host/VM; disk/crash/load work on the shared
Docker Desktop host can affect `jp_dev` even without touching its containers.
If the shared host is proposed, require explicit acceptance of that risk and hard
per-fixture memory/CPU/PID/storage limits with adequate measured host headroom.
Never fill the host/root filesystem or bind production data into a fixture.

Before any approved test, resolve project `phase6b_<approved-run-id>` into an
immutable manifest of **exact container IDs, image IDs, networks, ports and volume
names**. The role names below (`FB`, `COLLECTOR`, `LOKI`, `OS`, `TEMPO`, `PROM`,
`GRAFANA`, `GENERATOR`) refer exclusively to that manifest's clone, never matching
containers by broad substring. Require all new names to be absent before creating
the clone. The manifest must prohibit any `springboot_project_*`/`jp_dev_*` volume
or network attachment, real signing keys, live DB access, real accounts and
unapproved outbound transport. Use pinned existing images and synthetic data.

Start with constrained fixture storage (e.g.16–64MiB bounded tmpfs or a dedicated
small virtual disk) rather than using host free space as a limit. Approval must
choose numerical generator byte/event limits, request rate/concurrency, wall-clock
deadline, abort thresholds and observer. Abort on isolation mismatch, host headroom
below approved minimum, unexpected external traffic, unrelated-container change,
unbounded growth or unreadable evidence. Keep external notification egress blocked
except in the separately authorized E1 destination test.

Every test records UTC/config/image hashes, generated source event IDs/counts,
resource samples, queue/source lag, native metrics and backend query results.
Distinguish accepted, rejected, lost, duplicated and expired events. Never claim
exactly-once or zero-loss from an incomplete observation window. Rollback always
targets only manifest-owned fixtures; retain failed-test volumes/evidence until
explicit cleanup approval. Capture live IDs/start times/volumes before and after
to prove the production projects were not operated on.

## A. Disk-full, overflow and compressed rotation

### A1 — Fluent Bit destination-buffer exhaustion

- **Objective:** Measure per-output isolation, oldest-chunk discard and recovery.
- **Prerequisites:** Synthetic three-source file fixture; known per-output byte
  budgets; approved bounded record count and expected-loss tolerance.
- **Isolation:** Dedicated fixture network/disk and synthetic Loki/OpenSearch sinks.
- **Targets:** Manifest `FB`, its `fb_state` volume, `GENERATOR`, `LOKI`, `OS`.
- **Risks:** Intentional loss/duplicates, collector memory growth, shared-host IO.
- **Precautions:** Small fixture-only budgets/storage; hard generator cap/deadline;
  keep one destination healthy; never attach real source volumes.
- **Steps:** Emit uniquely numbered records; block only one fixture sink; cross
  its output budget; sample storage/retries/drops; restart only if separately
  included in approval; restore sink capacity/connectivity; wait bounded drain.
- **Expected:** Healthy sink continues; full output follows documented discard
  policy; recovery delivers retained data. Quantify any unexpected gaps.
- **Evidence:** Source/destination ID sets, per-output backlog/drop counters,
  memory/disk/time samples and drain duration.
- **Rollback:** Stop fixture generator, restore fixture sink, preserve state; leave
  live systems unchanged. Cleanup is separate.
- **Approval:** A1, exact IDs, budget, generator cap, outage duration and acceptable loss.

### A2 — Collector persistent queue saturation

- **Objective:** Verify byte admission bound, refusal behavior and later replay.
- **Prerequisites:** Synthetic OTLP generator, reduced fixture queue capacity,
  approved event/byte ceiling and unavailable fixture Tempo destination.
- **Isolation:** Clone-only disk/network; no application or real trace export.
- **Targets:** `COLLECTOR`, `collector_queue`, `TEMPO`, `GENERATOR`.
- **Risks:** Intentional span refusal/loss and compaction amplification.
- **Precautions:** Hard storage/resource limits; no blocking test that can back up
  a real application; sample queue size/capacity and receiver/export counters.
- **Steps:** Hold fixture destination unavailable; enqueue deterministic numbered
  spans to capacity; record refusals; stop generator; restore destination; drain.
- **Expected:** Admission stays bounded; full queue refuses new work; admitted
  retained spans can replay. Generic HELP units must not override configured bytes.
- **Evidence:** Attempted/admitted/refused IDs, queue DB/disk size, counters and
  Tempo results, duplicates and drain time.
- **Rollback:** Stop generator, restore fixture Tempo, retain failed fixture state.
- **Approval:** A2, capacity, maximum spans/bytes, duration and accepted loss.

### A3 — Backend storage exhaustion and pressure alarms

- **Objective:** Observe one backend's bounded disk-full behavior, upstream queues,
  pressure-alarm coverage and recovery after capacity restoration.
- **Prerequisites:** A dedicated fixed-size test disk; reliable fixture filesystem
  metrics/pressure alert source. Current live capacity alerts are unavailable.
- **Isolation:** Separate VM/disk required; never the shared Docker root filesystem.
- **Targets:** One approved `LOKI`, `OS`, `TEMPO` or `PROM` storage fixture per run,
  upstream fixture collectors and fixture-only Grafana alerts.
- **Risks:** Corruption, crash, deliberate loss, delayed compaction, host IO pressure.
- **Precautions:** Backend-specific clone, bounded temporary data, reserved recovery
  space, no production mounts; test each backend sequentially.
- **Steps:** Record baseline; gradually exhaust only the dedicated small test disk;
  observe writes/queries/upstream backlog and pressure alerts; stop input; enlarge
  or restore that disk's capacity without deleting arbitrary backend files; recover.
- **Expected:** Document real failure boundaries and recovery; pressure alerts fire
  only if their source is implemented/tested. Missing coverage is a test failure.
- **Evidence:** Filesystem/inode bytes, native errors, WAL/compaction state, exact
  source/destination ID comparison, alert timing and recovery readiness.
- **Rollback:** Detach/abandon the exhausted clone and recover from its known-good
  disposable snapshot; never repair live stores by deleting files.
- **Approval:** A3 separately per backend, disk identity/size, alarm instrumentation
  change, target ceiling and corruption/loss risk.

### A4 — Unread compressed rotation mitigation

- **Objective:** Reproduce the known gap and validate a proposed uncompressed
  archive collection/delayed-compression contract without duplicates or skips.
- **Prerequisites:** Fixture Logback/source writer and Fluent Bit using matching
  rollover limits/paths; reviewed candidate matching/compression/watermark design.
- **Isolation:** Fresh synthetic source/state volumes and clone outputs only.
- **Targets:** `GENERATOR`/fixture source writer, `FB`, source archive/state volumes,
  `LOKI`, `OS`; no real app logging config change.
- **Risks:** Wrong path patterns replay archives, inode reuse/duplicates, disk growth.
- **Precautions:** Distinct bounded filenames, no `.gz` tail inclusion, explicit
  disk/time limits and event IDs; retain original behavior as comparison fixture.
- **Steps:** Partially read a file; stop fixture collector; roll several files,
  including late old-inode writes; compress under original behavior and document
  missing IDs; repeat with candidate uncompressed retention/matching; restart;
  verify drain, truncation, inode reuse and delayed compression across restart.
- **Expected:** Original gap is reproducible; candidate meets an agreed maximum
  outage window without unread archive loss or unintended duplicate replay.
- **Evidence:** Source/archive manifests, offsets/inodes, destination ID sets,
  compression watermark/age and restart timing.
- **Rollback:** Abandon candidate fixture and keep current live config; deploy any
  eventual migration only under a separate reviewed application/collector rollout.
- **Approval:** A4 experiment and candidate design; production rollout is not included.

## B. Crash durability

### B1 — Hard Collector crash

- **Objective:** Test persistent queue recovery beyond ordinary restart evidence.
- **Prerequisites:** Synthetic known admitted spans, blocked fixture destination,
  queue/WAL state baseline and approved abrupt-stop mechanism.
- **Isolation:** Dedicated clone host/volume; production processes excluded by ID.
- **Targets:** `COLLECTOR`, `collector_queue`, `TEMPO`, `GENERATOR`.
- **Risks:** Queue corruption, fsync boundary loss, replay duplicates.
- **Precautions:** Stop generator at a recorded boundary; exact-ID assertion before
  abrupt termination; record admitted versus only batched/in-flight work.
- **Steps:** Queue numbered spans, abruptly terminate only fixture Collector,
  relaunch exact image/config/state, restore destination, compare resulting IDs.
- **Expected:** Measure actual admitted recovery and volatile loss; do not infer
  exactly-once from eventual delivery.
- **Evidence:** Precrash counters/queue files, timestamps, recovery logs and ID sets.
- **Rollback:** Restore fixture's pretest snapshot or retain corrupt state offline.
- **Approval:** B1 exact IDs, crash mechanism and accepted fixture loss.

### B2 — Hard Fluent Bit crash

- **Objective:** Verify tail-DB/chunk synchronization and source-position recovery.
- **Prerequisites:** Synthetic source sequence with known offsets, persistent fixture
  state, slow/unavailable fixture output and captured write boundary.
- **Isolation:** Clone-only source/state/output network and storage.
- **Targets:** `FB`, `fb_state`, synthetic source volumes, `LOKI`, `OS`.
- **Risks:** Tail/chunk inconsistency, duplicate replay, missing unflushed data.
- **Precautions:** Exact-ID termination and bounded source writer; don't edit DB/WAL.
- **Steps:** Emit numbered records, capture state, abruptly stop fixture FB, append
  bounded source data, restart same fixture state, restore sink and compare IDs.
- **Expected:** Quantified recovery/loss/duplicates; distinguish unread compressed
  history from chunks already persisted.
- **Evidence:** Source offsets/inodes, tail DB/WAL manifests, chunk metrics and sink IDs.
- **Rollback:** Preserve corrupt state and revert only disposable fixture snapshot.
- **Approval:** B2 exact IDs, source boundary, crash timing and acceptable loss.

### B3 — Backend crash during queued delivery

- **Objective:** Validate upstream retry plus backend WAL/idempotence behavior during
  an abrupt destination crash at a known delivery boundary.
- **Prerequisites:** Select one fixture backend and its collector, known synthetic
  source IDs, backend-consistent pretest backup and queue budget.
- **Isolation:** Dedicated clone host/volumes; sequential backend runs.
- **Targets:** One `LOKI`, `OS` or `TEMPO` plus `FB` or `COLLECTOR` and generator.
- **Risks:** Ambiguous acknowledgements, replay duplicates, corrupt backend WAL.
- **Precautions:** No live destination endpoints; exact-ID assertions and hard input cap.
- **Steps:** Deliver a known prefix, abruptly terminate fixture backend during
  continued bounded input; recover same store; let queues drain; query all IDs.
- **Expected:** Report actual acknowledged/unknown/lost/duplicated records, not an
  exactly-once claim; fresh writes/queries work after recovery.
- **Evidence:** Ack boundary, backend WAL/logs, queue counters, ID-set comparisons.
- **Rollback:** Abandon corrupt clone or restore its approved fixture backup.
- **Approval:** B3 per backend, crash mechanism, ID boundary and recovery budget.

## C. Natural retention deletion

For C1–C4, use genuinely aged synthetic fixture data or allow a short **supported
fixture-only retention** interval and wait naturally. Never alter timestamps,
creation dates or live retention to manufacture a pass. Approval must set storage
ceilings, observation interval and maximum wait; test-container health is not proof
of physical deletion.

### C1 — Loki expiration

- **Objective:** Prove policy execution, query expiry and physical chunk/index removal.
- **Prerequisites:** Supported short fixture retention or naturally aged fixture
  dataset; compactor/delete-delay settings and baseline object/file manifest.
- **Isolation:** `LOKI` clone with synthetic data and no live bucket/filesystem.
- **Targets:** `LOKI`, its compactor and `loki_data` fixture storage.
- **Risks:** Intentional deletion, compactor lag and filesystem accounting ambiguity.
- **Precautions:** Distinct expired/unexpired event groups; no manual delete requests.
- **Steps:** Ingest time-correct markers; wait past retention plus scheduling/delete
  delays; query both groups; compare physical manifests and native deletion evidence.
- **Expected:** Expired group disappears physically while retained group remains.
- **Evidence:** Config/UTC, compactor metrics/logs, query results and file/byte deltas.
- **Rollback:** Preserve the clone evidence; restore fixture snapshot if needed.
- **Approval:** C1 retention/delay settings, wait ceiling and synthetic deletion scope.

### C2 — OpenSearch index deletion

- **Objective:** Observe native ISM transition and actual fixture index deletion.
- **Prerequisites:** Dedicated time-correct synthetic index family and test policy;
  short supported age threshold or naturally aged fixture indices; backup manifest.
- **Isolation:** `OS` clone, never live application or system indices.
- **Targets:** `OS` fixture policy/index UUIDs and corresponding disk store.
- **Risks:** Policy wildcard overreach, irreversible test-index deletion.
- **Precautions:** Exact fixture index prefix/UUID allowlist; no global templates.
- **Steps:** Create approved fixture family, attach test policy, wait naturally,
  observe explain state/action, verify index404 and store reclamation/lag.
- **Expected:** Only expired fixture UUIDs delete; unexpired control stays intact.
- **Evidence:** Policy/explain progression, index UUID/catalog, query/disk evidence.
- **Rollback:** Restore only fixture snapshot into new fixture indices.
- **Approval:** C2 exact policy/index allowlist, threshold and maximum wait.

### C3 — Tempo trace expiration

- **Objective:** Verify natural block retention and physical block removal.
- **Prerequisites:** Fixture traces with current timestamps, supported retention/
  compaction settings, known trace IDs and block manifest.
- **Isolation:** `TEMPO` clone; no shared trace storage.
- **Targets:** `TEMPO`, compactor, fixture WAL/blocks.
- **Risks:** Intentional trace loss, live-block/WAL retention timing ambiguity.
- **Precautions:** Separate expired/control cohorts; wait for block completion.
- **Steps:** Ingest markers, observe blocks, wait naturally beyond retention and
  compaction lag; query trace IDs and compare block manifests.
- **Expected:** Expired blocks/queries disappear; control cohort remains queryable.
- **Evidence:** UTC/block IDs, compactor observations, trace queries and bytes/files.
- **Rollback:** Restore disposable snapshot if needed; live data untouched.
- **Approval:** C3 retention settings, ID cohort, storage and wait limits.

### C4 — Prometheus retention enforcement

- **Objective:** Observe supported time/size retention and reclaimed persisted blocks.
- **Prerequisites:** Fixture-only TSDB and generator; choose time or size mechanism
  explicitly; inspect WAL/head overhead separately from block retention budget.
- **Isolation:** `PROM` clone on dedicated bounded storage; no remote writes to live.
- **Targets:** `PROM`, fixture TSDB, synthetic scrape generator.
- **Risks:** Expected sample deletion, WAL/head growth beyond block-size budget.
- **Precautions:** Hard generator/storage limits, retained control series/ranges.
- **Steps:** Produce timestamp-correct samples; wait for normal block compaction and
  chosen supported retention trigger; compare old/new queries and block manifests.
- **Expected:** Document actual retention enforcement and extra WAL/head space;
  don't equate configured size with a hard disk quota.
- **Evidence:** Active flags, block time ranges/sizes, compaction observations and queries.
- **Rollback:** Stop fixture input, preserve TSDB and recover from fixture snapshot.
- **Approval:** C4 specific time/size limits, byte ceiling and observation duration.

## D. Backup integrity and disposable restore

### D1 — Consistent backup creation and integrity

- **Objective:** Establish recoverable, encrypted, off-host backups and manifests.
- **Prerequisites:** Approved destination/credentials, agreed RPO/RTO targets,
  native mechanism/version review and consistency/quiescence plan per store.
- **Isolation:** Prefer fixture backups first. Any live backup/quiescence requires
  explicit additional maintenance authorization; no source mutation by default.
- **Targets:** Manifest Grafana, Prometheus, Loki, OpenSearch, Tempo, queue/tail/source
  state and separately managed database/key backups in [backup-restore.md](backup-restore.md).
- **Risks:** Inconsistent hot copies, secret leakage, IO pressure and incomplete state.
- **Precautions:** Encryption/access limits, safe manifest, full WAL/state sets,
  no unapproved admin API enablement or repository registration.
- **Steps:** Execute reviewed per-store native/consistent backup, wait completion,
  inspect native status, hash artifacts, transfer off-host, verify decryption/readability.
- **Expected:** Integrity/consistency evidence for every included component; incomplete
  coverage is explicit and does not pass the recovery gate.
- **Evidence:** UTC/config/image/checksum manifest, native status, storage/access checks.
- **Rollback:** Stop backup job and restore approved config if changed; retain originals
  and restrict failed/secret-bearing artifacts, without deleting live data.
- **Approval:** D1 exact scope/destination/credentials handling and any maintenance.

### D2 — Restore, data verification and recovery-time measurement

- **Objective:** Prove recoverability and measure actual RPO/RTO rather than promise it.
- **Prerequisites:** D1 validated backups, expected sample/trace/event IDs, approved
  sanitized test dataset and documented restore sequence.
- **Isolation:** Fresh destination volumes/network; never restore over original data.
- **Targets:** All approved backend/state roles plus `GRAFANA` in the isolated clone.
- **Risks:** Overwritten clone state, replay duplicates, encrypted-secret mismatch,
  accidental live notifier/database connection.
- **Precautions:** Exact destination IDs, egress blocked, all-day mute preserved,
  datasource/DB endpoints checked before starting restored collectors/apps.
- **Steps:** Verify backup; restore backend stores; restore queue/tail/source sets;
  start collectors; restore Grafana last; query historical/control/fresh data and
  replay IDs; time service-ready and data-ready boundaries.
- **Expected:** Verified artifacts, matching required data, documented loss/duplicates
  and measured RPO/RTO within pre-approved objectives, or an explicit failed gate.
- **Evidence:** Native restore status, counts/checksums/sample queries, ID sets,
  startup/replay timings and unchanged live IDs/volumes.
- **Rollback:** Abandon the isolated restored clone; do not roll data onto live stores.
- **Approval:** D2 backup/destination manifests, dataset handling, resource limits and objectives.

## E. External notification delivery

### E1 — Authorized destination, grouping/repeat/recovery and mute behavior

- **Objective:** Verify actual delivery and resolved messages with expected grouping,
  repeat intervals and mute/unmute semantics.
- **Prerequisites:** Explicitly authorized test recipient/webhook, destination owner,
  transport secrets through approved secret store, allowed payload and message cap.
- **Isolation:** `GRAFANA` clone/test contact point only; existing production mutes,
  contacts, policies and thresholds remain untouched.
- **Targets:** Fixture rule group/contact point/route and exact approved destination.
- **Risks:** Real messages, accidental recipient/payload leakage, repeated spam.
- **Precautions:** Allowlist destination, cap messages, test labels only, no user data,
  bounded duration and observer with ability to block fixture egress immediately.
- **Steps:** Start muted and prove no sends; enable only fixture test delivery;
  drive synthetic Normal→Pending→Firing; verify grouped sends/repeat; restore normal;
  verify recovery; remute; confirm silence and stop fixture timer/generator.
- **Expected:** Correct recipients, bounded grouping/repeat, recovery received and
  mutes respected; SMTP/webhook success is not inferred from rule evaluation alone.
- **Evidence:** Sanitized sender/destination acknowledgements, UTC/message IDs,
  notification timing/status and unchanged live policy/contact digests.
- **Rollback:** Remute fixture, disable its transport/egress and remove only approved
  disposable test resources after evidence; never unmute live rules.
- **Approval:** E1 exact recipient/URL privately, message cap, window, payload and observer.

## F. Representative performance

### F1 — Bounded request/telemetry/query and recovery-capacity test

- **Objective:** Establish representative request/telemetry capacity, overhead and
  query latency with measured abort thresholds and backlog recovery.
- **Prerequisites:** Approved workload mix/RPS/concurrency/duration, realistic
  sanitized DB fixtures, test keys, metrics baseline and acceptance thresholds.
- **Isolation:** Separate host preferred; complete app/backend clone; no real accounts,
  key regeneration, live DBs or shared load targets.
- **Targets:** Fixture User/Learning/JWKS, test DBs, collectors, backends and Grafana.
- **Risks:** CPU/memory/storage contention, excessive logs/cardinality, false paging.
- **Precautions:** Rate/concurrency/total-request caps, staged ramp, isolated egress,
  storage ceiling, automatic abort and on-call observer; no unbounded soak.
- **Steps:** Measure baseline; ramp approved traffic in bounded steps; query dashboards
  concurrently; measure telemetry bytes/events, queue lag/drain, API latency/errors,
  pools/GC/RSS/CPU, backend growth and query latency; stop at deadline/abort; drain.
- **Expected:** Explicit sustainable tested envelope and overhead/recovery limits;
  failures are reported, not extrapolated into untested production RPS claims.
- **Evidence:** Workload definition, time series, cardinality, losses/duplicates,
  resource/storage growth, API/query percentile latency and recovery time.
- **Rollback:** Stop generator first; keep fixtures within budget, drain or preserve
  state; original environments remain unchanged.
- **Approval:** F1 numeric load/byte/resource/time caps, dataset, objectives and abort rules.

## G. Timed internal lifecycle without external delivery

### G1 — Normal → Pending → Firing → Resolved

- **Objective:** Verify real elapsed scheduler/pending/keep-firing transitions.
- **Prerequisites:** Disposable Grafana/datasource clone and deterministic synthetic
  metric schedule; no production rules or data source mutations.
- **Isolation:** Clone only, egress blocked and all notifications muted throughout.
- **Targets:** `GRAFANA`, `PROM` or fixture datasource, unique synthetic rule group.
- **Risks:** Stale synthetic firing rules, schedule/jitter misinterpretation.
- **Precautions:** Exact test UID allowlist, bounded end time, constant low cardinality.
- **Steps:** Create fixture metric/rule, observe normal; hold breach beyond its
  pending period; observe firing; restore metric; wait keep-firing interval;
  observe resolved; remove only fixture-owned resources after evidence approval.
- **Expected:** Actual UTC transition times agree with interval/pending/recovery
  semantics including scheduler tolerance; no external delivery.
- **Evidence:** State history/API captures, rule export, metric schedule and no-send proof.
- **Rollback:** Stop schedule and preserve/stop isolated Grafana; no live state affected.
- **Approval:** G1 exact rule/data source IDs, timing, clone scope and cleanup boundaries.

## Review decision

Choose which individual tests to authorize; approval of this document alone is not
execution authorization. Reject any execution manifest that names production
volumes, `jp_dev` resources or real external destinations without specific consent.
After each approved test, update evidence and readiness classifications separately.
Do not convert historical ordinary-restart results into crash/restore/deletion PASS.

## 2026-11-12 remediation clarification

An explicitly authorized, isolated ordinary collector-downtime/rotation test was completed as remediation, using new fixture volumes and protocol sinks. It did not interrupt live collection to inject failure. Stable-name uncompressed spool files now avoid immediate compression and renamed-file checkpoint replay. Twelve checks/52 events per sink are evidence for that bounded scenario only; update future crash/overflow fixtures to this new source layout.

All Phase6B gates above remain in force: no disk exhaustion, hard crash, backend crash, forced expiry/deletion, destructive restore, external delivery or representative load was executed. Future tests must measure retained-file expiration/size-cap eviction, output acknowledgement ambiguity, duplication and hard-crash windows separately. A successful graceful restart is not crash proof.

The [secure-production candidate](secure-production/README.md) also requires approved credentials/PKI, a separately named isolated clone with new volumes, native positive/negative access tests, consistent backup/restore proof and coordinated rollback review before live activation. Structural validation is not approval to alter the existing OpenSearch security index. No existing production volumes,16`jp_dev` containers or `japanese-learning` resources may be used for isolated failure injection.
