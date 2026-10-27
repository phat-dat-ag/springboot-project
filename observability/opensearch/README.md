# Local OpenSearch logging

Run from C:\Personal\springboot-project. The existing Compose project name is
**springboot_project** (underscore). Always pass it to reuse its network and volumes.

## Start

Docker Desktop must be running. Its Linux VM needs vm.max_map_count >= 262144;
the verified host already meets this requirement.

~~~powershell
docker compose -p springboot_project config --quiet
docker compose -p springboot_project up -d --no-deps --wait opensearch opensearch-dashboards
docker compose -p springboot_project restart fluent-bit
powershell -NoProfile -ExecutionPolicy Bypass -File .\observability\opensearch\setup-dashboards.ps1
~~~

These commands assume the existing application, Loki, and Fluent Bit are running.
For a fresh installation, configure the existing .env requirements and run
docker compose -p springboot_project up -d --build.

- OpenSearch: http://localhost:9200
- Dashboards: http://localhost:5601/app/discover
- Select springboot-user-logs*, with @timestamp as the time field.
  Choose the last 15 minutes and refresh.
- The setup script creates a missing index pattern or refreshes its field list
  from the live index mapping, preserving existing settings and the default pattern.
- If Dashboards reports a missing @timestamp index-pattern-field, rerun the setup
  script and reload the browser. Log ingestion must have started before setup.

## Verify ingestion

~~~powershell
Invoke-RestMethod http://localhost:9200/_cluster/health
Invoke-RestMethod http://localhost:5601/api/status
$response = Invoke-WebRequest -UseBasicParsing http://localhost:8080/actuator/health/readiness
$response.Headers['X-Correlation-ID']
# Allow about 10 seconds for Fluent Bit's flush and OpenSearch's refresh.
Invoke-RestMethod http://localhost:9200/springboot-user-logs/_count
docker compose -p springboot_project logs --since 2m fluent-bit
~~~

Search Discover using correlationId: "YOUR-ID".
USER_API_HOST_PORT may override the default 8080.
Fluent Bit continues sending the same records to Loki.

## Startup diagnosis

The shared restrictions set read_only: true. OpenSearch needs to write its
keystore under /usr/share/opensearch/config; an isolated diagnostic reproduced
FileSystemException for opensearch.keystore.tmp. Dashboards startup also needs
to remove its disabled security plugin and write runtime state. Only these two
services override read_only. Non-root users, dropped capabilities,
no-new-privileges, and resource limits remain in place.

The 3.9.0 image's optional Performance Analyzer agent separately reported
ClassNotFoundException for PerformanceAnalyzerApp. That unused agent is disabled.
Both services use matching 3.9.0 images; Dashboards waits for OpenSearch health.

Fluent Bit needed a restart to load its added OpenSearch output. Generate_ID
prevents duplicates during output retries; Suppress_Type_Name supports modern
bulk requests. Existing tail offsets are preserved, so already consumed logs
are not automatically replayed.

## Scope and persistence

This is a local development setup with security plugins disabled and host ports
bound to 127.0.0.1, not a configuration for public exposure.
OpenSearch data and Dashboards saved objects persist in opensearch_data.
Existing application logic, database services, Loki output, and Grafana
configuration are unchanged. No automatic log retention is configured.
The existing Fluent Bit memory buffer is unchanged; this does not add a durable
outage queue.

Do not use docker compose down -v to troubleshoot: it deletes project data.
Inspect health and logs instead:

~~~powershell
docker compose -p springboot_project ps
docker compose -p springboot_project logs --tail 100 opensearch opensearch-dashboards fluent-bit
~~~

References:
- https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/
- https://docs.opensearch.org/latest/install-and-configure/install-dashboards/docker/
- https://docs.fluentbit.io/manual/data-pipeline/outputs/opensearch


