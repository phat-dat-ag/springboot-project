# Production observability readiness — Phase 6A

Assessment date: 2026-11-12. **Overall production readiness: FAIL for the current
deployment.** Development telemetry works; production incident delivery, durability,
recovery and representative capacity have not been established. This is an
assessment of this deployed configuration, not an assertion that the products are
incapable of production operation.

## Separate readiness conclusions

| Area | Result | Evidence / qualification |
| --- | --- | --- |
| Development observability | PASS | Real requests, dual-store JSON logs, nine scrape targets, actual distributed traces, eight dashboards and 300 Maven tests |
| Operational monitoring | PASS | Current service/pipeline queries and health checks work; backend capacity alerts and browser checks remain gaps |
| Internal alert evaluation | PASS | 21 rules healthy; thresholds, labels, pending/recovery configuration and synthetic previews verified; elapsed lifecycle unverified |
| External incident notification | NOT VERIFIED | Delivery disabled by all-day mute; no email/webhook sent |
| Data durability | FAIL | Immediate compressed rollover can strand unread history; crash/overflow durability is also unverified |
| Backup and recovery | NOT VERIFIED | No OpenSearch snapshot repository configured; no consistent backup/restore rehearsal or measured recovery objectives |
| Production capacity | NOT VERIFIED | Only bounded development samples; no representative workload/soak or storage alerting |
| Overall production readiness | FAIL | Confirmed data-collection/access-control gaps plus critical unverified acceptance gates |

## Confirmed failures versus missing evidence

The current OpenSearch security plugin is disabled. Loki, Tempo, Collector and
Prometheus rely on a trusted plaintext Docker bridge; selected administration
ports bind only to loopback. This preserves the existing development boundary but
does not supply production authentication, TLS or per-workload network isolation.
Do not expose these endpoints or attach untrusted containers. Grafana authentication
and private API scrape authorization passed; they do not protect every backend.

Logback writes exact current files and immediately gzips archives. Fluent Bit tails
only those current files. An unread file compressed during collector downtime is
not available to the tail input after restart. Filesystem buffering protects only
data already admitted to Fluent Bit, not unread application archives. See the
concrete mitigation in [operations-runbook.md](operations-runbook.md).

The ten NOT VERIFIED findings are distinct from failures: privileged User access
with an admin test account; browser rendering/clicks; real elapsed alert lifecycle;
external notification/recovery delivery; crash/overflow durability; physical
retention deletion; backup integrity/restore; production load capacity; live async
endpoint behavior; backend storage-pressure alerting. Existing non-admin 403,
authenticated Learning and internal User access passed. Async/MDC behavior passed
in isolated Maven fixtures; no public async test endpoint was added.

## Evidence and scope

[phase6-verification.md](phase6-verification.md) is the A–S report.
[phase6-checklist.md](phase6-checklist.md) contains the current check results and
historical acceptance rows from Phases 0–5. Historical passes are not new evidence.
[phase6-measurements.json](phase6-measurements.json) contains allowlisted measured
values, versions and current test counts. Raw local run snapshots/results live in
ignored `observability/phase6-evidence/`; no JWTs or credential values are stored.

The successful complete run returned **exit1**, deliberately reflecting two
verified readiness failures: 750 PASS, 2 FAIL, 10 NOT VERIFIED, 2 NOT APPLICABLE.
This is not an infrastructure-test crash or a green production gate. Exit2 is
reserved for incomplete evidence without verified failures; exit0 means all
requested executed criteria passed with no remaining required evidence gap.

## Release gates

Before claiming full production readiness, establish the actual production network
and TLS/authentication design; validate loss-window mitigation; approve responder
ownership, SLOs and alert thresholds; verify authorized delivery including recovery;
rehearse consistent backups/restores with measured RPO/RTO; validate actual storage
expiry, capacity alarms, crash recovery and representative performance. Browser
acceptance must cover filter/link interpolation and native visualizations.

These changes/tests are **not authorized by completing Phase 6A**.
[phase6b-validation-plan.md](phase6b-validation-plan.md) requires a separate approval
with exact targets, resource ceilings, acceptable loss, destinations and rollback.
No restart, service outage, overflow, crash, deletion, restore or external send was
executed during Phase 6A. No runtime configuration was changed.

## Remediation follow-up — 2026-11-12

The preceding statement describes the original Phase6A run. The separately authorized [remediation](phase6a-remediation.md) subsequently applied logging configuration: three sequential API recreations using existing images and one graceful Fluent Bit configuration restart. Databases/backends/Grafana and all16`jp_dev` containers were unchanged; original93 volumes and historical samples remained intact.

| Readiness area | Current conclusion |
|---|---|
| Development observability | PASS for executed bounded regression; browser/positive-admin gaps remain |
| Operational monitoring | PASS for collected coverage,9 targets/5 recording rules/8 dashboards; disk-capacity coverage incomplete |
| Internal alert evaluation | PASS for21 healthy rules/preview; elapsed lifecycle NOT VERIFIED |
| External incident notification | NOT VERIFIED; mute remains active, no sends |
| Ordinary retained-file collection recovery | PASS for isolated immutable-spool rotation/restart and live dual-store delivery |
| Data crash/overflow durability | NOT VERIFIED; finite retention/queue limits and duplicate windows remain |
| Backup/recovery and physical retention deletion | NOT VERIFIED |
| Production capacity | NOT VERIFIED |
| Production telemetry security | FAIL / OPEN; native secure candidate NOT DEPLOYED |
| Overall production readiness | FAIL / NOT DEMONSTRATED |

Do not approve live security activation solely from a successful structural check. [Required PKI, migration/rollback and isolated negative tests](secure-production/README.md) remain prerequisites. No JWT/JWKS contract or `japanese-learning` change is required.

## Phase6B isolated follow-up — 2026-11-12

See [executed verification](phase6b-verification.md), [acceptance matrix](phase6b-test-matrix.md) and [sanitized measurements](phase6b-measurements.json). The dedicated lab exercised native TLS/mTLS and OpenSearch certificate roles, container SIGKILL/queue recovery, intentionally lossy bounded overflow, five-store restore rehearsals, natural OpenSearch physical deletion, elapsed Grafana lifecycle and local notifications. Original Phase6A/remediation evidence remains unchanged.

These results apply to disposable memory-backed stores, synthetic traffic and test-only PKI. Existing development services were not restarted or migrated. **Deployed production telemetry security remains FAIL/OPEN.** Real application SSL bundles/metrics proxies, positive password/Dashboards integration, host/storage durability, dedicated backend disk-full/pressure alerts, complete Loki/Tempo/Prometheus expiry, off-host recovery, representative capacity, browser behavior and external provider delivery remain NOT VERIFIED or BLOCKED.

Local native TLS, internal alert lifecycle and restore evidence improved; full Phase6B acceptance and overall production readiness remain unestablished. No production RPO/RTO or capacity objective is promised. `japanese-learning` needs no changes. Review the scoped evidence before separately authorizing any live migration.
