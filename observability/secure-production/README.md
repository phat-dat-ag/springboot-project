# Inactive secure-production candidate

**Do not apply this overlay to existing live volumes.** It has passed structural Compose checks only. Native secure startup, PKI, authentication, authorization, migration and recovery remain NOT VERIFIED. The development deployment remains plaintext and OpenSearch security remains disabled. This directory does not resolve the live Phase6A security failure.

## Configuration

`compose.json` is an explicit Compose overlay, never loaded by default. JSON is supported by Compose and the YAML-reading components used here. Generated source is `../build-secure-candidate.py`; review generated diffs if regenerating. Do not regenerate after hand editing candidate files without incorporating those edits in the generator.

| Files | Purpose |
|---|---|
| `compose.json` | Read-only per-service TLS mounts, native TLS settings, five private metrics proxies; existing named data volumes retained |
| `*-metrics-tls.conf` | mTLS GET-only metrics on9092 for APIs,2021 for Fluent Bit,8889 for Collector; all other paths denied |
| `fluent-bit.conf` | Verified TLS and client certificates for the Loki output and three service-specific OpenSearch outputs; original tail databases/buffers and spool strategy |
| `collector.yml` | mTLS OTLP4318 and verified TLS client to Tempo4317; persistent queue retained; plaintext metrics/health loopback |
| `loki.yml`, `tempo.yml` | Verified-client HTTPS query/metrics endpoints and encrypted ingestion; single-binary internal RPC listeners loopback |
| `prometheus*.json`, `targets/` | HTTPS/mTLS web and scrapes, original instance identities, nine targets; separate Grafana metrics basic authentication |
| `datasources/` | Stable existing UIDs, verified TLS, existing log/trace navigation; PEMs supplied by environment |
| `alerting.json` | Same21 rules with production environment and existing delivery mute |
| `opensearch.yml`, `opensearch_dashboards.yml` | Native security plugin, HTTP/transport TLS, mandatory client certs, authenticated backend connection and HTTPS UI |
| `security-config.example/` | Reviewable bootstrap examples, not deployable credentials or complete vendor role definitions |

The five proxies are pinned to an existing nginx image digest and bounded to32MiB/0.25CPU each; no additional metric pipeline is introduced. They share the owner's network namespace. **Build new API images containing `app.metrics.listener.address` support before using the overlay.** The live logging rollout deliberately reused old images, which do not contain this optional Java change. Without that new image the original9091 listener remains bridge-accessible and bypasses the proxy. Confirm socket binds before acceptance.

## Required configuration variables

Copy `.env.secure.example` to an ignored location; preserve existing root `.env`. All variables below are required only by the explicit secure overlay, have no defaults, and are unused in development. Required interpolation fails closed. Never commit filled values.

| Variable | Purpose / security handling |
|---|---|
| `OBS_TLS_DIR` | Absolute existing directory of authorized per-service PKI files; read-only mounts, no auto-creation |
| `OS_SECURITY_CONFIG_DIR` | Reviewed complete bootstrap directory with supplied bcrypt hashes; ignored, restricted access |
| `OS_ADMIN_DN` | Exact approved admin certificate DN; separate offline administrative identity |
| `OS_NODE_DN` | Exact approved transport-node certificate DN; never use the admin identity as node identity |
| `OS_DASHBOARDS_PASSWORD` | Existing authorized `dashboards_svc` password matching supplied hash; secret |
| `OBS_GRAFANA_ROOT_URL` | Approved HTTPS operator URL matching certificate/ingress |
| `GRAFANA_METRICS_PASSWORD` | Dedicated Prometheus-only metrics credential, also stored in the Prometheus password file |
| `GRAFANA_TLS_CA_PEM` | Authorized datasource CA PEM; multiline environment value |
| `GRAFANA_TLS_CLIENT_CERT_PEM` | Authorized Grafana datasource client certificate PEM |
| `GRAFANA_TLS_CLIENT_KEY_PEM` | Matching private PEM; secret, never print expanded environment |

For every service directory under `OBS_TLS_DIR` (`user-api`, `learning-api`, `jwks-api`, `fluent-bit`, `otel-collector`, `loki`, `tempo`, `prometheus`, `grafana`, `opensearch`, `opensearch-dashboards`), supply only required files: `ca.pem`, `server.crt`/`server.key` for servers, `client.crt`/`client.key` for clients. The three API directories also supply metrics server keys. Prometheus additionally needs `grafana-metrics-password` matching the metrics credential. File ownership must permit the actual container UID (including proxy10001) to read its own key and prevent unrelated access. Mount only each service's directory, not a shared directory of all keys.

Use an approved dedicated telemetry CA and distinct leaf identities. Server SANs must match actual Compose DNS names (and approved host browser names); certificates need appropriate serverAuth/clientAuth EKUs and valid chains/lifetimes. OpenSearch transport identity must match configured node DN and hostname; HTTP certificate must cover `opensearch`. OpenSearch health client CN is `opensearch-health`; Fluent Bit client CN is `fluent-bit`. Use supported unencrypted PKCS8 key encoding for the OpenSearch file-based configuration with restrictive file permissions; obtain policy approval for container-readable keys. Do not use demo certificates, disable hostname checks, or generate/install production keys as part of this task. Configure expiry monitoring/renewal before activation.

## Isolated validation and migration procedure — NOT EXECUTED

1. Obtain explicit migration approval, authorized PKI and hashes/passwords. Inventory existing index UUIDs/counts, ISM policies, Grafana state, targets, old traces/logs, volume identities and key fingerprints. Schedule a window and define recovery ownership. Do not restart unrelated projects or databases.
2. Establish and verify an OpenSearch native snapshot repository and successful snapshot. Back up existing security configuration with the native `securityadmin.sh -backup` mechanism if a security index already exists. A copied live data directory is not a demonstrated consistent backup. Do not overwrite an existing security index from examples.
3. Prepare bootstrap files in an ignored new directory using existing authorized bcrypt hashes:

   ```powershell
   python observability/prepare-opensearch-security.py --output data/secure-opensearch --dashboards-hash-file <ignored-existing-hash-file> --operator-hash-file <ignored-existing-hash-file>
   ```

   This reads vendor reserved roles/action groups/tenants from the pinned3.9.0 image without starting OpenSearch or contacting a backend; it never generates credentials. Inspect the completed files privately. Retain vendor reserved definitions; example role files alone are incomplete. Hashes and output directory are sensitive. Do not copy vendor demo users. `telemetry_writer` allows bulk/create/index only for three dated application-index families; `telemetry_health` grants cluster health only. Admin and Dashboards roles must be separately reviewed.
4. Create a separately named disposable project/network and **new** volumes. Build new API images. Copy the configuration with explicit replacement of `container_name`, networks, host ports, app dependencies and data volumes; do not start the root overlay under a second project without auditing inherited fixed names and bind paths. Restore the approved snapshot into that isolated OpenSearch cluster according to vendor restore procedures. Never mount live data volumes in the test cluster.
5. Start the isolated OpenSearch with native security and no default automatic security-index initialization. Bootstrap only its new security index using the bundled3.9.0 `securityadmin.sh` over verified TLS with the approved admin certificate, CA, exact cluster name/hostname and reviewed directory. Do not use hostname/cluster verification bypass flags. For an existing index, export, merge and apply a reviewed change instead of replacing it. Health may remain unhealthy until bootstrap grants the health certificate its role. Verify vendor CLI options for the pinned image before invoking them; no bootstrap command was run in this remediation.
6. Start isolated backend clients and metrics proxies with supplied files. Confirm all plaintext metrics bind127.0.0.1; the old9091/2020/8888 ports must be inaccessible from other namespaces. Confirm only intended metrics GET paths pass the proxies. Verify TLS hostname/CA/client authentication on every hop, all nine scrapes, Grafana datasource UIDs, eight dashboards, five recording rules,21 evaluations and notification mute. Verify the Prometheus HTTPS readiness command and every component's native configuration/startup; structural validation alone does not prove this.
7. Negative tests: missing/unknown client certificate rejected; wrong CA/hostname fails; unauthorized index read/write denied; Fluent Bit cannot access unrelated indices or security APIs; health identity cannot read logs; Grafana UI still requires login and its metrics endpoint rejects absent/wrong basic auth. Existing trusted client certificates authorize broad single-tenant Loki/Tempo/Prometheus access; document that trust scope rather than claiming per-route ACLs.
8. Verify Fluent Bit creates new permitted dated indices, Loki accepts safe JSON, OpenSearch retains old index UUIDs/counts after restore, and native ISM policy assignment/explain succeeds through authenticated HTTPS. Existing HTTP retention-install scripts are **not** secure-compatible; migrate those operational calls to verified TLS admin credentials before activation. No Grafana OpenSearch datasource exists today, so no hidden datasource credential migration is assumed. Dashboards backend credential must match its hash/role and browser authentication must be tested.
9. Exercise bounded isolated normal traffic and verify dual-store source event identity, trace export, old data readability, health startup order and certificate renewal behavior. Record positive and negative HTTP/TLS results without credentials. Test rollback and snapshot recovery on disposable storage. Preserve evidence before any live decision.
10. Only after those gates, approve a separate coordinated live migration. Native TLS changes require client/backend coordination; it is not a zero-interruption toggle. Keep application source spool and collector queues intact during the window. Keep external notifications muted. Reconcile all historical resources and data before acceptance.

Rollback: stop rollout on any failed native startup, unreadable historical data, unauthorized acceptance or growing delivery backlog. Restore previous configurations/images and original connection modes in coordination; never delete the data directory or security index. Security-index changes require an approved backed-up configuration restore and may make a simple flag rollback insufficient. Validate the rollback on the isolated copy first. No such recovery is claimed verified here.

## Safe checks available now

```powershell
python observability/validate-secure-candidate.py --structure
python observability/validate-secure-candidate.py
```

The first uses synthetic interpolation values **only in memory**, performs Compose/static checks and starts nothing. Exit0 means structural validation only. The second returns2 while prerequisites or runtime verification remain outstanding. Neither initializes security, creates certificates, tests a handshake or authorizes activation. Do not print `docker compose config` for a real filled environment; it expands secrets.
