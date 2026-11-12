# Disposable Phase6B laboratory

This harness never inherits the root Compose configuration. It generates a dedicated `springboot_phase6b` model under ignored `data/phase6b/<UTC-run-id>/`, with an internal network, no host publications, no external volumes, per-run labels and tmpfs-backed stores with explicit byte ceilings. It uses pinned locally available backend images and synthetic producers; no application databases, JWT keys, existing credentials or existing containers are test dependencies.

Results apply only to the isolated lab. The existing deployment remains plaintext with OpenSearch security disabled. A passing isolated TLS handshake does not activate production security or establish production capacity.

## Commands

From the root in PowerShell:

```powershell
python -m unittest discover -s observability/phase6b -p test_safety.py -v
python observability/phase6b/lab.py prepare
python observability/phase6b/lab.py validate
python observability/phase6b/lab.py start
python observability/phase6b/lab.py test --suite security
python observability/phase6b/lab.py test --suite opensearch
python observability/phase6b/lab.py test --suite crash
python observability/phase6b/lab.py test --suite overflow
python observability/phase6b/lab.py test --suite lifecycle
python observability/phase6b/lab.py test --suite performance
python observability/phase6b/lab.py test --suite backup
python observability/phase6b/lab.py test --suite retention
python observability/phase6b/lab.py preserve
python observability/phase6b/lab.py collect
python observability/phase6b/lab.py stop
```

`data/phase6b-current.json` selects the current run. Preparation refuses overlapping Compose resources. Generate fresh test credentials on a new run; never import root `.env`. The test environment file is generated and ignored. `.env.example` explains the two Grafana test-only variables; neither has any production meaning. Production and development PKI must never be copied into this directory.

The supported suite order above creates backup controls before restoration. Individual suite invocations can be retried after diagnosing a failure; each result is retained. Do not blindly rerun backup into a populated restore volume. Stopping is exact-ID/label scoped; it does not delete containers, networks, volume definitions or evidence.

`--suite backup-native` resumes only native Prometheus/OpenSearch snapshot testing after successful cold-copy checks. Native Prometheus WAL and block-chunk segments are16MiB in this lab so snapshot preallocation fits the128MiB store. Defaults caused an observed, isolated ENOSPC snapshot failure before this adjustment; no host filesystem was filled. Collect forensic source/queue/repository copies before stopping the anchor. They are evidence, not verified consistent backups.

Test exit codes:0 means the selected executed checks passed,1 a verified failure,2 BLOCKED/NOT VERIFIED evidence remains in that invocation. Historical unsuccessful attempts remain in results but do not silently replace or invalidate later scoped observations. Exit0 never means production readiness.

## Limits and safety gates

- No published ports, inherited networks, container names or shared namespaces; all Docker mutations verify exact project/run labels.
- The rendered model rejects existing volumes, external networks, unrelated bind paths, writable configuration mounts and missing resource ceilings. Only the run's evidence directory is a writable host bind.
- Source cap4MiB/suite, at most512 log records/batch,300 trace IDs/batch. Bounded performance envelope:10logs/sec for10sec and20 spans, serial queries. No API stress test.
- Source volume8MiB; Fluent Bit16MiB; Collector queue16MiB; logical output limits64KiB Loki/1MiB OpenSearch; serialized trace queue16KiB. Backend stores128MiB each except Grafana64MiB and OpenSearch768MiB. Snapshot repository128MiB. A separate2MiB tmpfs is the only target of an intentional physical ENOSPC fill.
- Every service has explicit CPU, memory, swap, PID and Docker log bounds. Native OpenSearch needs a writable layer for its startup keystore and executable, bounded temporary storage; disk-full injection is never directed at that writable layer. Native data/repository/log/temp paths use bounded mounts.
- Abort floor:2GiB host `MemAvailable`, checked before suites/mutations and during bounded load. A test invocation has a30min suite budget with per-request/subprocess/wait deadlines; independent invocations preserve separate timings. Long tests should run under an operator able to stop the lab. This is a shared-host fixture, not a dedicated performance host.
- Fixture metrics/control/notification HTTP endpoints stay inside the internal test network. Native backend queries, ingestion, Grafana and Prometheus scrapes use TLS; native metrics proxy/application image activation remains a separate gate. No external notification recipient or egress network is configured.

All test stores are **memory-backed**. The probe holds mounts while backend containers stop/crash, so those tests measure container-process recovery, not host-crash or power-loss persistence. When the last volume mount closes, tmpfs contents can disappear even though the Docker volume definition remains. Capture backups/manifests/evidence before stopping the anchor. Never describe these volumes as durable backup media.

## Credentials and evidence

`prepare` creates a new two-day test CA, an untrusted CA, distinct server/client identities, an administrative certificate, reader/writer identities and a replacement-client identity using an existing OpenSSL binary in a network-disabled bounded helper. Key usage, constraints, SANs and EKUs are explicit; verification is never bypassed. Test material resides only under ignored `data/`. The helper does not regenerate any existing JWT key.

The probe is a privileged *test orchestrator identity*, with access to fixture client identities for positive/negative checks and fixture stores for backup observation. It must never be deployed as a production service. Backend identities receive their own leaf directory. Security roles are assembled from the pinned vendor reserved role definitions; no vendor default users are copied. OpenSearch certificate authentication is tested independently from username/password or browser SSO integration.

`evidence/results.json` records every attempt with command, start/end, elapsed time, expected/actual outcome and evidence location. Other artifacts include immutable baseline, rendered-model hash/allowlist, exact resource inventory, resource samples, event reconciliation, queue counters, state transitions, local notification payloads, backup manifests/checksums and retention observations. The fully rendered secret-bearing model and PKI are not publishable artifacts. Do not attach them to a PR or public report.

## Cleanup

Collect/report evidence first. The harness deliberately retains Docker resources and host evidence. To delete *only* this run's disposable Docker resources after review, explicitly supply its exact run ID:

```powershell
python observability/phase6b/lab.py cleanup --confirm <exact-current-run-id>
```

Without that confirmation cleanup refuses before any action. It stops only matching project/run IDs, removes only those exact containers, validates each exact volume/network label and removes those resources individually. No global prune, wildcard volume selection or `down -v` is used. It never deletes host evidence, certificates or backups. No volume-deleting cleanup was executed by this task.

See [verification report](../phase6b-verification.md) and [test matrix](../phase6b-test-matrix.md) for actual execution results and remaining gaps.
