# Observability backup and restore runbook

**Assessment only. No backup creation, restore or data replacement was executed in
Phase6A. Restore success and RPO/RTO are NOT VERIFIED.** OpenSearch reports no
registered snapshot repositories. Prometheus's admin API is disabled. No verified
backup scheduler, off-host retention, integrity monitoring or recovery objective
was found in this repository. External organizational backups, if any, were not
visible to this assessment and must not be assumed absent or working.

## What must be protected

| Component | Reconstructible from Git | Persistent backup / consistency requirement |
| --- | --- | --- |
| Grafana | Provisioned dashboards, datasource definitions, rule definitions and mute | `grafana_data`: SQLite database/WAL plus users, personal dashboards, contacts/policies, encryption configuration and installed plugin versions. An API export alone is not complete user/state backup |
| Prometheus | Scrape config, target files, recording rules | `prometheus_data`: TSDB blocks, WAL and head. Use native snapshot with head included or an approved quiesced/storage-consistent copy; live arbitrary file copies are not a verified backup |
| Loki | Config/schema/retention | Whole `loki_data`: chunks/index, WAL, compactor working/retention marker state at one consistent point |
| OpenSearch | Versioned lifecycle/template installer; installer must not be rerun blindly | Native snapshots of application indices/metadata in a registered off-host repository; don't treat a live copy of Lucene data directories as a supported snapshot |
| Tempo | Config | Whole `tempo_data`: WAL and blocks coherently; account for traces still in Collector/app buffers |
| Collector | Pipeline/queue configuration | `otel_queue`: DB, journal and compaction state as one consistent set; replay can duplicate already delivered data |
| Fluent Bit | Parser/tail/output configuration | `fluent_bit_state`: all tail SQLite DB/WAL files and filesystem chunks, coordinated with application current/archive log files and inode/path semantics |
| Source application logs | Logback configuration | Three log volumes: exact current files and relevant archives. Stale tail offsets with mismatched source files can skip or duplicate records |
| Secrets and keys | Examples only, never live credentials/key material | Original ignored env files, Grafana encryption secret/config, API signing keys/public files and required repository credentials in approved encrypted secret backup; preserve key IDs/issuers |
| Application databases | Migration source only | MySQL/PostgreSQL require their own native consistent database backup/PITR plan. Copying Docker volumes live is not validated here |

All named volumes currently use the `springboot_project_` prefix. Inventory actual
mount identities, image IDs, ownership, modes, config hashes, retention and snapshot
timestamps in a protected manifest. Include checksums, backup encryption/key-access
procedure, destination authorization, retention/expiry owner and restore manifest.
Keep backup media off the Docker data disk and separate from this Git checkout.
An export containing secrets must never be checked into Git or public evidence.

## Prepare a backup — plan, not a tested procedure

1. Define RPO, RTO, target restore timestamp, loss/duplicate tolerance and data
   owners; none are established today. Confirm authorized encrypted destination,
   free capacity, credentials, network access and provider/version compatibility.
2. Export reviewed Git revision/image digests, safe Grafana definitions and topology
   for reconstruction. Grafana provisioning does not cover users, passwords,
   personal resources or all secrets; protect its actual database separately.
3. For Grafana SQLite, use an approved SQLite-consistent online backup mechanism
   with a compatible client, or schedule a quiesced backup after stopping only
   Grafana. A plain copy of the running DB without WAL consistency is insufficient.
   Do not install a client or stop Grafana as part of Phase6A.
4. Prometheus supports `POST /api/v1/admin/tsdb/snapshot` only with its admin API
   enabled. It is currently disabled; do not enable it on the live deployment just
   for an assessment. In an approved isolated/maintenance workflow, include head
   data (`skip_head=false`), record the returned snapshot path, and copy that
   immutable snapshot to the encrypted backup location. Enabling an admin endpoint
   needs a separate access-control review. Alternative: approved consistent cold
   storage copy with known downtime/data-loss bounds.
5. Register an authorized native OpenSearch snapshot repository only after
   provisioning its required storage, permissions/plugin and `path.repo` or
   object-store credentials. Use application-index scope deliberately, preserve
   required mappings/templates/ISM policies and avoid a global-state restore over
   unrelated indices/users. Wait for native snapshot SUCCESS and shard results;
   repository listing/verification alone does not prove a successful backup.
6. For filesystem Loki/Tempo and collector state, use a storage-consistent snapshot
   or approved quiescence. Coordinate source writers/collectors, flush what can be
   flushed, record remaining volatile data and stop only specifically approved
   target components for a cold copy if necessary. Copy whole state sets with UID/
   GID/modes. Do not mix queue/tail DB generations or assume a hot tar is consistent.
7. Hash backup artifacts, encrypt and transfer off-host, verify readable manifest
   and native metadata, and rehearse restoration into disposable volumes. A
   checksum proves byte integrity, not application recoverability. Record which
   backups include in-flight traces/logs and which can replay duplicates.

Native mechanisms and constraints are documented by
[Grafana backup guidance](https://grafana.com/docs/grafana/latest/administration/back-up-grafana/),
[Prometheus snapshot API](https://prometheus.io/docs/prometheus/3.12/querying/api/#snapshot),
[OpenSearch native snapshot/restore](https://docs.opensearch.org/latest/opensearch/snapshot-restore/)
and [Loki storage](https://grafana.com/docs/loki/latest/configure/storage/).
Commands/options must be checked against the pinned installed versions before
approved execution. These references do not establish a successful local restore.

## Restore into a disposable environment — Phase6B only

1. Obtain separate authorization naming the manifest, backup, isolated Compose
   project/host, storage ceiling and acceptable exposure. Require a dedicated
   network, loopback test ports, no live volume mounts, no shared database access
   and no external notification transport. Prefer another Docker host for storage
   and failure tests so `jp_dev` cannot suffer shared resource pressure.
2. Verify checksums/encryption access and create new destination volumes. Restore
   the exact images/config schema first, matching non-root UID/GID and permissions.
   Keep original volumes immutable and disconnected. Never reuse `springboot_project`
   or `jp_dev` as a test project name.
3. Restore backend data first: native OpenSearch snapshot into isolated indices;
   consistent Loki/Tempo stores; Prometheus snapshot data with its own lock/WAL
   handling. Start/query backends before allowing buffered replay. Restore
   application databases via their independent native recovery process if the
   rehearsal includes authenticated traffic; no live production user/account
   records may be used without an approved protected test dataset.
4. Restore queue/tail/source-log sets coherently, then start collectors with
   destinations pointing exclusively to restored backends. Measure replay, missing
   event IDs, duplicate IDs, queue drain and source position. A byte-identical tail
   DB on changed file/inode identity is not a guaranteed correct restore.
5. Restore Grafana database/config/encryption material last, point its datasources
   at restored backends, retain delivery-disabled mutes and disable all external
   notifier network paths. Verify users/login safely, all dashboards/rules/policies,
   actual historical/fresh records and expected sample trace IDs.
6. Measure recoverable timestamp/RPO and elapsed service/data-ready times/RTO.
   Validate signed manifests, counts/checksums, representative source IDs and
   actual queries; do not infer success from healthy containers alone.
7. Stop only test components after evidence collection. Retain failed restore data
   for investigation; cleanup of disposable artifacts is separately scoped and
   approved. Rollback is abandoning the isolated clone and preserving the original
   deployment, not restoring over live volumes.

No numerical recovery objective is promised until agreed and demonstrated. Queue
snapshots are not a substitute for source/backend backup, and retention replicas
or a persistent Docker volume are not backups.

## Phase6B disposable restore rehearsal — 2026-11-12

[Executed evidence](phase6b-verification.md) now verifies separate-target recovery of synthetic Grafana, Prometheus, Loki, OpenSearch and Tempo state. Grafana/Loki/Tempo used quiesced complete store copies with checksummed artifacts; Prometheus used its native head-inclusive snapshot; OpenSearch used a native SUCCESS snapshot and separate security-initialized cluster. Test queries verified API-created Grafana state,12 log controls and3 trace controls where applicable. These improve the historical NOT VERIFIED state only for this isolated rehearsal.

Prometheus default snapshot preallocation exceeded the128MiB fixture tmpfs; supported16MiB WAL/block-chunk segment settings allowed snapshot/restore at the same bounded capacity. Preserve that failed attempt as a capacity finding. Native OpenSearch global/security state was excluded from data restore and initialized separately; this is not an existing-security-index migration rehearsal.

The lab is memory-backed and holds mounts with a probe anchor during container stops. Backups/manifests were exported before shutdown. Forensic hot queue/source/repository copies are not application-consistent backup proof. No live backup, off-host encryption, production secret recovery, host-crash durability or agreed RPO/RTO is claimed. Existing volumes were never restored over. Use the original approval-gated production procedures above for real systems.
