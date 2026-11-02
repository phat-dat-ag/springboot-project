# Application logs in Grafana and Loki

## Open in your browser

For the current local environment:
- Grafana: http://localhost:3077
- Application logs: http://localhost:3077/d/springboot-application-logs/application-logs
- Explore: http://localhost:3077/explore
- Loki readiness: http://localhost:3177/ready

Sign in with the existing Grafana account. Initial administrator credentials come
from GRAFANA_ADMIN_USER and GRAFANA_ADMIN_PASSWORD in .env. If the account password
was changed in Grafana, use that password; changing .env does not reset an existing
account. Credentials are not included in dashboard files.

The dashboard is in the Observability folder. Select services and log levels at
the top, choose a time range, and expand a log entry to inspect its JSON fields.
It defaults to the last 15 minutes with a 10-second refresh. It includes log rate
by service and up to 1,000 recent log entries. Narrow the time range or use Explore
for more targeted searches.

Compose defaults are Grafana port 3000 and Loki port 3100. The current .env uses
3077 and 3177 instead. Use docker compose -p springboot_project ps to see actual
published ports. No index-pattern setup is required for Loki.

## Start or apply configuration

Run from the repository root with Docker Desktop running and the application
stack already configured:

```powershell
docker compose -p springboot_project config --quiet
docker compose -p springboot_project up -d loki grafana fluent-bit
docker compose -p springboot_project restart fluent-bit
```

The restart reloads the mounted Fluent Bit configuration. Grafana provisions its
Loki datasource and dashboard on startup. Dashboard JSON changes are scanned every
30 seconds. Provider or datasource configuration changes require restarting Grafana.
For a fresh installation, configure the existing environment files and start the
whole stack with docker compose -p springboot_project up -d --build.

The dashboard is managed in Git. Edit dashboards/application-logs.json to change
it, or save a separate copy in Grafana for personal customization.

## Pipeline and queries

Fluent Bit reads the existing JSON files from all three application volumes and
sends the same records to OpenSearch and Loki. Loki streams have these labels:

| Label | Values |
| --- | --- |
| job | springboot |
| service | user, learning-api, jwks-service |
| environment | development |

The service label is read from each JSON record. Request IDs and other fields stay
inside the log record rather than becoming high-cardinality stream labels.

In Explore, choose the Loki datasource and use LogQL in Code mode:

```logql
{job="springboot"}
```

```logql
{job="springboot", service="learning-api"}
```

```logql
{job="springboot"} | json | level="ERROR"
```

```logql
{job="springboot"} | json | correlationId="YOUR-CORRELATION-ID"
```

The dashboard's service and level selectors apply to both panels. WARN/ERROR
filters can legitimately return no results when there are no matching events.

## Verification and troubleshooting

```powershell
docker compose -p springboot_project ps loki grafana fluent-bit
Invoke-RestMethod http://localhost:3077/api/health
Invoke-WebRequest -UseBasicParsing http://localhost:3177/ready
Invoke-RestMethod http://localhost:3177/loki/api/v1/label/service/values
docker compose -p springboot_project logs --since 5m --tail 100 fluent-bit loki grafana
```

Generate a request, copy its correlation ID, allow about ten seconds for collection,
and search in Explore:

```powershell
$response = Invoke-WebRequest -UseBasicParsing http://localhost:8781/actuator/health/readiness
$response.Headers['X-Correlation-ID']
```

The current Learning and JWKS application ports are 8782 and 8783. A healthy Loki
datasource can also be checked under Connections > Data sources > Loki > Save & test.
If logs appear absent, select All services and levels, widen the time range, and
check collector errors. A brief readiness failure during startup can be retried.

Existing tail offsets are preserved. Learning and JWKS records consumed before
their Loki output was enabled are not replayed; newly written records are collected.
Do not delete tail databases or Docker volumes to force replay.

## Persistence and scope

Loki uses loki_data for local storage and has 720-hour (30-day) retention configured
through its compactor. Grafana accounts and saved objects persist in grafana_data.
The collector retains separate checkpoints for each application in fluent_bit_state,
initialized with the non-root collector's ownership before startup.

This is a single-host development setup. Host ports bind to 127.0.0.1, Loki has no
authentication, and Grafana retains its existing login requirement. Fluent Bit uses
memory buffering, so it does not provide a durable outage queue. Do not run
docker compose down -v: that removes project data.

References:
- https://grafana.com/docs/grafana/latest/administration/provisioning/
- https://docs.fluentbit.io/manual/4.1/data-pipeline/outputs/loki
