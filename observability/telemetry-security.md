# Telemetry access-control assessment — 2026-11-12

**Live status: production security failure remains open.** Development host access is loopback-only; that does not authenticate containers on the shared bridge or encrypt traffic. The secure-production configuration is an inactive candidate, not evidence of deployed security.

## Observed endpoints

The runtime socket inventory is [remediation-endpoints.json](remediation-endpoints.json). All listed services currently share `springboot_project_default`. `::` denotes the observed wildcard socket; Docker's `127.0.0.11` ephemeral DNS socket is not an application endpoint. Published addresses below bind **127.0.0.1 only**. No unnecessary wildcard host publication was found, so existing development ports were preserved.

| Component | Container listeners | Host access | Current authentication / authorization | Current TLS / required clients |
|---|---|---|---|---|
| User API | `::`:8080,9091 | 8781→8080 | Application JWT rules; dedicated metrics connector/path restriction | Plain HTTP; clients, Learning API, Prometheus |
| Learning API | `::`:8080,9091 | 8782→8080 | Application JWT rules; dedicated metrics connector/path restriction | Plain HTTP; clients, User API/JWKS dependencies, Prometheus |
| JWKS API | `::`:8080,9091 | 8783→8080 | Public JWKS/health contracts; restricted metrics path/connector | Plain HTTP; both roots' JWKS consumers, Prometheus |
| Grafana | `::`:3000 | 3077→3000 | UI/API authenticated; existing `/metrics` is unauthenticated | Plain HTTP; host operators, Prometheus, outbound datasource queries |
| Prometheus | `::`:9090 | 9090→9090 | No query authentication; admin/lifecycle APIs disabled | Plain HTTP; Grafana and local operators; outbound nine scrapes |
| Loki | `::`:3100,9095 | 3177→3100 | Single-tenant, no HTTP authentication | Plain HTTP/gRPC; Fluent Bit, Grafana, Prometheus |
| Tempo | `::`:3200,4317,9095,7946 | None | Single-tenant, no application-level authentication | Plain HTTP/gRPC/memberlist; Collector, Grafana, Prometheus |
| OpenSearch | `::`:9200,9300 | 9277→9200 | Security plugin disabled; no index ACLs | Plain HTTP/transport; Fluent Bit, Dashboards, local retention/health operations |
| Collector | `::`:4318,8888,13133 | None | No OTLP/metrics authentication | Plain HTTP; APIs export4318, Prometheus8888, health13133 |
| Fluent Bit | `0.0.0.0`:2020 | None | No metrics authentication | Plain HTTP; Prometheus; outbound Loki/OpenSearch |
| OpenSearch Dashboards | 5601 configured | 5677→5601 | Security plugin disabled with current backend | Plain HTTP; host operators, outbound OpenSearch |

There are no separate infrastructure exporters; six native infrastructure targets plus three applications produce the nine scrapes. OpenSearch has no collected Prometheus health/capacity exporter. Public-port Actuator metrics requests are rejected by the application connector boundary; internal metrics remain readable by arbitrary bridge peers. This is a network/path boundary, not production client authentication. Existing Grafana and JWT authentication were preserved and regression-tested.

## Security model and limits

Host-local development access is deliberately retained. A compromised host, a privileged Docker client, or an unrelated container attached to the bridge can read or submit private telemetry. The Compose network alone cannot close this gap. Native single-tenant Loki/Tempo flags are not authorization mechanisms.

The [secure-production candidate](secure-production/README.md) uses native TLS/mTLS for ingestion, scraping and backend queries; native OpenSearch security for index authorization; authenticated HTTPS Grafana; and five narrowly scoped TLS metrics proxies for components without suitable native HTTPS metrics support. Those proxies share the owning component's network namespace, with the plaintext listener restricted to loopback. A single shared gateway would leave a direct plaintext bridge bypass unless the deployment was substantially re-networked. No proxy was started in the live stack.

The candidate still grants a trusted client certificate broad access to single-tenant Loki/Tempo/Prometheus APIs. Use a dedicated observability CA/issuance policy, separate client identities, restricted network membership and certificate revocation/rotation. Multi-tenant query/write authorization, Internet ingress, an external identity provider and network policy require a separately reviewed production architecture. Do not expose these raw ports to the Internet. Application business HTTP/JWT contracts are outside this telemetry migration and unchanged.

## Verification boundaries

- PASS: all current publications remain loopback-only; ingestion and metrics ports remain unpublished; Grafana authentication and protected public-port Actuator behavior still work.
- PASS: existing telemetry flows, nine scrapes, five recording rules, eight Phase5 dashboards and 21 muted alert rules continue to work after the logging rollout.
- IMPLEMENTED BUT NOT DEPLOYED: TLS/mTLS configuration, restricted OpenSearch writer/health roles, configurable application metrics bind address, metrics proxies, environment prerequisite checks.
- NOT VERIFIED / BLOCKED: production certificates, HTTPS handshakes, rejection of unauthorized clients, native secure startup, OpenSearch security-index bootstrap/migration, credential rotation and restore. No authorized production PKI or security bootstrap credentials were available. Enabling the plugin against live data without those tests would risk interrupting delivery.

No certificates, passwords, JWT signing keys or accounts were generated or changed. Examples contain placeholders only; keep actual material outside Git and avoid printing expanded Compose environments, datasource secure fields or bootstrap hashes.

## Phase6B isolated security evidence — 2026-11-12

The preceding no-generation statement describes remediation; the subsequently authorized Phase6B lab generated **new disposable two-day test PKI and a test-only Grafana credential**, without reading/replacing any existing signing key or password. Native TLS1.3, trusted-client success, missing/untrusted-client rejection, wrong CA/hostname rejection, real secured log/trace ingestion and Grafana proxy queries passed in `springboot_phase6b`. OpenSearch admin/writer/reader certificate roles and native security-index initialization/restart/restore were tested. Positive password, Dashboards/SSO, production application/proxy activation and certificate root/hot-server rotation remain unverified.

No secure overlay was enabled on `springboot_project`. Its plaintext trust boundary and disabled OpenSearch security remain the same confirmed production security failure. The lab uses a private test-only HTTP control/notification plane and native collector/Fluent Bit metric observations; this is explicitly not complete production-profile hardening. [Full evidence and scope](phase6b-verification.md) distinguish isolated success from live security activation.
