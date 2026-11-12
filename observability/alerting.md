# Grafana Unified Alerting — Phase 5

Alert evaluation is deployed; **external notification delivery is NOT VERIFIED
and remains muted**. Open Grafana → **Alerting → Alert rules → Observability →
springboot-phase5**. Do not treat this installation as production-ready paging.

## Rules and thresholds

[alert-rules.md](alert-rules.md) lists all 21 rules with exact PromQL, stable UID,
threshold, severity, pending period, no-data behavior and investigation instructions.
The source is `build-phase5.py`; its generated Grafana-supported API version 1 JSON
file is mounted read-only at `provisioning/alerting/phase5.json`. Grafana 12.2.0
loaded and evaluated it successfully. The exact version's
[provisioning implementation](https://github.com/grafana/grafana/blob/v12.2.0/pkg/services/provisioning/alerting/rules_types.go)
supports rule-local `notification_settings`, keep-firing and no-data/error fields.

| Alert | Threshold / minimum traffic | Pending | Severity |
| --- | --- | --- | --- |
| ServiceDown | Application `up < 1` | 2m | critical |
| MissingMetricsUser/Learning/JWKS (3 rules) | Expected `up` absent for 5m | additional 2m | warning |
| High5xxErrorRate | 5xx fraction >5%; ≥100 requests/5m | 5m | critical |
| HighHTTPErrorRatio | 4xx+5xx fraction >20%; ≥100 requests/5m | 10m | warning |
| HighP95Latency | >1s; ≥100 requests/5m | 10m | warning |
| HighP99Latency | >2.5s; ≥1000 requests/5m | 15m | warning |
| HighHeapUsage | Heap/positive maximum >85% | 15m | warning |
| HighCPUUsage | Process CPU fraction >85% | 15m | warning |
| ExcessiveGCPause | Pause time/wall time >10% | 10m | warning |
| HikariPoolSaturation | Active/positive maximum >90% | 10m | warning |
| HikariPendingConnections | Pending >0 | 5m | warning |
| CollectorExportFailures | Failed span-export attempts rate >0 | 5m | warning |
| CollectorQueueSaturation | Queue size/positive capacity >80% | 5m | critical |
| FluentBitDeliveryFailures | Output-error/exhausted-retry/dropped-record rates >0 | 5m | warning |
| LokiIngestionFailures | HTTP push 4xx/5xx or chunk-flush failure rate >0 | 5m | warning |
| TempoUnavailable | Tempo metrics `up < 1` | 2m | critical |
| PrometheusTargetDown | Other infrastructure metrics `up < 1` | 3m | warning |
| ElevatedAuthenticationFailures | >50 failed terminal operations/10m | 5m | warning |
| ElevatedAuthorizationDenials | >100 denials/10m | 10m | warning |

All evaluate every **1 minute**, keep firing for **1 minute** after recovery and
carry severity/environment/phase labels. Service comes from the aggregated query
labels; missing-target rules supply an explicit canonical service. Pool dimension
is bounded by actual pool names. No route/user/request/trace labels create alert
instances. Scrape availability is not an end-to-end business availability check.
`PrometheusTargetDown` does not duplicate the separate Tempo or application alerts.

Availability rules use `NoData` for total-query disappearance; all other rules use
`OK` when no series exists. Missing-target rules explicitly detect expected
application series absence. All use `execErrState: Error`, exposing evaluator or
datasource failures separately instead of hiding them as healthy. A disappeared
individual series is resolved by Grafana's missing-series handling; it is not
proof of business recovery. No-data and execution-error instances can lack dynamic
service labels. Inspect Grafana health even when ordinary rules are Normal.

Volume guards prevent low-traffic percentage/tail alerts. Heap/CPU/pool thresholds
are initial development defaults, not approved production SLOs. GC pause alerts use
actual pause-time counters, not an invented GC histogram. Failed exporter attempts
may be retried successfully. Fluent Bit's summed error signal is not a unique lost
record count. Loki push and flush failures do not cover every possible discard
reason. HTTP authentication operation failures include input/server failures;
neither every 401 nor every failed login establishes an attack.

## Routing and delivery safety

The pre-existing default contact point and notification policy tree are preserved.
There were no existing alert rules or Prometheus alerting rules. Prometheus owns
only five recording rules; Grafana Unified Alerting is the sole new alert evaluator.
No Alertmanager server or second metrics pipeline was introduced.

Each Phase 5 rule uses rule-local routing to `$PHASE5_ALERT_RECEIVER`. Compose sets
the existing default receiver name `grafana-default-email` unless explicitly
overridden. An all-day provisioned mute interval, `phase5-delivery-disabled`, applies
to every rule. It is loaded and verified via Grafana's mute-timings API. Rules
remain active internally. Merely setting a recipient or receiver variable does
**not** enable Phase 5 delivery. No test messages were sent to real recipients.

Routing groups by **service, environment, severity**, waits **1 minute**, groups
updates every **5 minutes**, repeats every **4 hours**. Recovery notifications are
supported by the optional webhook's `disableResolveMessage: false`, but remain
muted and unverified. Rule-local settings avoid replacing an operator's policy
tree. Do not provision a new `policies` root over the existing tree.

For a future authorized webhook destination:

1. Obtain explicit authorization for the destination and test delivery. Put its URL
   in ignored `.env` as `GRAFANA_ALERT_WEBHOOK_URL`, never in Git or dashboard JSON.
2. Review `grafana/notification-webhook.json.example` and
   `grafana/docker-compose.notifications.yml.example`. They are not loaded by
   default. The override passes the environment variable and mounts the example
   at a real `.json` provisioning path. Use it as the last `-f` from the project
   root with the base/debug files; do not change the Compose project name.
3. Provision the authorized contact point while keeping all rules muted. Confirm
   the `phase5-webhook` name/UID and URL privately; do not print the URL.
4. Set `PHASE5_ALERT_RECEIVER=phase5-webhook` in ignored `.env`. Review the generated
   rules' mute settings in a separate delivery-enablement change, retain grouping
   and repeat intervals, and run an explicitly authorized test including recovery.
5. Enable only after verifying destination delivery, access controls, payload
   privacy, silences and responder ownership. Keep a local export of existing
   policies/contact points before changing them.

For email, configure the existing Grafana SMTP/contact-point facility with
environment-provided host, user, password and sender; the safe variable names are
listed in `.env.example`. No SMTP transport or recipients were invented or enabled
here. These email placeholders are documentation, not active Compose mappings.

Use expiring **Silences** scoped to environment/service/severity during maintenance,
with owner, reason and end time. For recurring approved maintenance, add a separate
bounded mute timing and reference it in rule-local settings. Never remove the
delivery-disabled interval as an incidental maintenance change. Do not pause all
evaluation merely to suppress notifications; retain internal visibility.

## Applying and investigating

For initial/reviewed application of these files:

```powershell
python observability/build-phase5.py --environment development
python observability/verify-phase5.py static
python observability/verify-phase5.py preflight
python observability/verify-phase5.py native
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build --pull never grafana prometheus
python observability/verify-phase5.py runtime
python observability/test-phase5-alerts.py
```

Capture a fresh baseline for a new deployment under a new ignored evidence filename;
the snapshot helper refuses to overwrite the original Phase 5 baseline. Preflight
uses the initial deployment baseline; on later deployments compare expected owned
UIDs as updates rather than new-object collisions. Never blindly replace unrelated
resources. Dashboard-only edits are scanned; alert file edits need a Grafana restart
or supported admin reload; Prometheus recording-rule edits need SIGHUP. Readiness
may take a short startup interval; run runtime validation after endpoints respond.

Start an investigation with the rule's description/runbook, then the relevant
dashboard, target `lastError`, safe logs and sampled traces. For Collector queue
saturation, restore the destination and inspect export failures; do not erase the
persistent queue. For Fluent Bit delivery failures, inspect the affected output
and existing internal storage API; never delete tail DBs to force replay. Check
OpenSearch via its existing loopback health API and inspect application primaries;
the known system-index replica yellow status is not an application outage.

## Explicitly unavailable alerts and production follow-up

**NOT IMPLEMENTED:** HighDiskUsage and StorageCapacityRisk: no reliable collected
backend/host filesystem capacity source. Application `disk_free_bytes` is scoped
to application mounts and cannot stand in for all Docker volumes. No OpenSearch
cluster-health alert exists because no Prometheus exporter is installed. No
Fluent Bit per-output buffer-utilization alert exists because that capacity ratio
is not exposed in its collected Prometheus endpoint. No standalone cryptographic
token-validation failure alert exists because it is not separately instrumented.

Phase 6 review can decide host/storage instrumentation, measured capacity budgets,
TLS/network policy, responder ownership, backups/restore and outage/disk-full/crash
acceptance. Those changes were not implemented in Phase 5. Browser clicks,
elapsed pending/recovery transitions under a real breach, prolonged outages and
external delivery remain explicit unverified gates. Synthetic preview checks
exercise breach/normal/no-data/execution-error query evaluation without modifying
services or persisting synthetic alert rules.
