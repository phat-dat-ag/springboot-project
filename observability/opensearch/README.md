# Local OpenSearch application logs

Run commands from C:\Personal\springboot-project. Always use Compose project
name springboot_project to reuse the existing network and data volumes.

## Open in your browser

The current local environment publishes:
- Dashboards: http://localhost:5677
- Saved Application logs view: http://localhost:5677/app/discover#/view/springboot-application-logs-view
- OpenSearch API: http://localhost:9277
- User / Learning / JWKS APIs: ports 8781 / 8782 / 8783

These ports come from local environment overrides. Compose defaults are 5601
for Dashboards and 9200 for OpenSearch. Check actual bindings with:
~~~powershell
docker compose -p springboot_project ps
~~~

Open Discover, select springboot-*-logs*, choose Last 15 minutes, and refresh.
The Application logs saved search includes service, level, message, HTTP fields,
and correlationId. Set an automatic refresh interval in the time picker if desired.

Example DQL filters:
- service: "user-learning"
- service: "learning-api"
- service: "jwks-service"
- level: ERROR
- correlationId: "YOUR-ID"

## Start and configure

Docker Desktop must be running. Its Linux VM needs vm.max_map_count >= 262144.
For an existing stack:
~~~powershell
docker compose -p springboot_project config --quiet
docker compose -p springboot_project up -d opensearch opensearch-dashboards fluent-bit
powershell -NoProfile -ExecutionPolicy Bypass -File .\observability\opensearch\setup-dashboards.ps1 -DashboardsUrl http://localhost:5677
~~~

For a fresh installation, configure .env, .env.user-api and .env.jwks-api from their matching .example files
and run docker compose -p springboot_project up -d --build first.
Use your actual Dashboards port when running setup. Run setup after ingestion starts.

The setup script creates or refreshes the combined index pattern with @timestamp
as its time field, selects it as default if none exists, and creates the
Application logs saved search if missing. Existing saved-search customizations
and existing default-index choices are preserved. Rerunning setup is supported.

You can also create the pattern manually under Management > Dashboards Management
> Index patterns: enter springboot-*-logs*, then select @timestamp.

## Pipeline and scope

JSON application log files are mounted read-only into Fluent Bit:
- User: /logs/user-api.log -> springboot-user-logs
- Learning: /learning-logs/learning-api.log -> springboot-learning-logs
- JWKS: /jwks-logs/jwks-api.log -> springboot-jwks-logs

Fluent Bit adds environment=development and flushes every five seconds.
All three applications also send logs to Loki; see the [Grafana guide](../grafana/README.md).
Each input has its own persistent SQLite tail
checkpoint. Generate_ID prevents duplicate documents on output retries.

The fluent-bit-state-init service fixes ownership of the state volume to
10001:10001 before Fluent Bit starts. It reuses the stack's postgres image for
shell utilities, has no network, and only mounts the collector state volume.
The collector itself remains non-root with a read-only root filesystem.
Without initialization, a root-owned state volume causes:
cannot open database /fluent-bit/state/user-api.db.

## Verify and troubleshoot

~~~powershell
docker compose -p springboot_project ps
Invoke-RestMethod http://localhost:9277/_cluster/health
Invoke-RestMethod 'http://localhost:9277/_cat/indices/springboot*?format=json'
Invoke-RestMethod http://localhost:5677/api/status
docker compose -p springboot_project logs --tail 100 fluent-bit opensearch opensearch-dashboards
~~~

Call an application's readiness endpoint, record the response X-Correlation-ID,
allow about ten seconds, then search for that ID in Discover. Example:
~~~powershell
$response = Invoke-WebRequest -UseBasicParsing http://localhost:8781/actuator/health/readiness
$response.Headers['X-Correlation-ID']
~~~

If Discover reports a missing @timestamp field, rerun setup and reload the browser.
If no results appear, widen the time range and check the collector logs.
The log indexes use default replica settings; on this single-node development
cluster, yellow health can mean an unassigned replica while all primary data
remains searchable.

Do not use docker compose down -v to troubleshoot: it deletes project data.

## Persistence and limitations

OpenSearch data and Dashboards saved objects persist in opensearch_data.
Tail offsets persist in fluent_bit_state. Previously consumed records are not
automatically replayed. Active files are read from the beginning on first use;
compressed archived log files are not imported.

This is a local development setup: security plugins are disabled, host ports
bind to 127.0.0.1, and the cluster has one node. No automatic OpenSearch retention,
rollover, or durable Fluent Bit outage queue is configured. Application log-file
rotation does not remove indexed documents. HTTP status and elapsed_ms are
currently strings; numeric latency aggregations need explicit mapping/conversion.

OpenSearch and Dashboards use matching 3.9.0 images. Their vendor startup needs
writable root filesystems, while other runtime restrictions remain enabled.
The unused Performance Analyzer agent is disabled.

References:
- https://docs.opensearch.org/latest/dashboards/management/index-patterns/
- https://docs.opensearch.org/latest/dashboards/discover/index-discover/
- https://docs.fluentbit.io/manual/data-pipeline/outputs/opensearch
