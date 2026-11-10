# Phase 0 deployed-runtime verification

Date: 2026-11-09. Final backend check: **10:43:05 UTC / 17:43:05 Asia/Bangkok**.
This supplements the earlier [source/configuration baseline](phase0-baseline.md).
It does not implement or authorize Phase 1.

## Result

**PASS:** Phase 0 configuration is deployed in `springboot_project`. User, Learning
and JWKS are healthy; fresh logs contain the canonical identity, release version,
and environment in application stdout, Loki and OpenSearch. Live login, JWKS and
Learning-to-User service authentication passed. No unexpected OTLP export errors
or collector error/flush-failure lines were found in the checked startup windows.

No source/configuration repair was required during this deployment. Only this
verification report and links to it were added to the Phase 0 documentation.

## Deployment scope and preservation

Project detection found `springboot_project` using this repository's base and debug
files. `jp_dev` uses `C:/Personal/japanese-learning/docker-compose.yml` and was never
targeted by deployment commands. The existing debug override was retained.

| Container | Action | Reason / final state |
| --- | --- | --- |
| `springboot_project-jwks-api-1` | Image rebuilt; container recreated first | New application/Logback metadata; healthy before caller recreation |
| `springboot_project-user-api-1` | Image rebuilt; container recreated | New identity/exporter defaults; healthy |
| `springboot_project-learning-api-1` | Image rebuilt; container recreated | New identity/exporter defaults; healthy |
| `springboot_project-fluent-bit-1` | Recreated using existing image | Load shared environment and mounted collector configuration; running |

Exactly these four containers changed identity. Before/after comparison verified:

- **25 unrelated containers unchanged**, including all **16 `jp_dev` containers**
  (running and stopped): IDs, images, start times, restart counts, ports, mounts
  and network memberships matched.
- Target containers retained published HTTP/debug ports, effective mount sources,
  destinations/access modes and network memberships. Fluent Bit's image was unchanged.
- **10 protected environment/key-file fingerprints matched**. No RSA key was
  generated/replaced and no real environment file was edited.
- User and Learning JWKS responses, RSA public key material, content type and
  `Cache-Control: max-age=300, public` were identical before and after deployment.
- Existing databases, named volumes, tail checkpoints and unrelated backends were
  retained. No `down`, volume deletion, pruning, forced recreation, migration
  runner execution, or unrelated-service update was performed.

Docker Desktop changed the collector bind source's representation from a Windows
path to `/run/desktop/mnt/host/c/...`. A literal comparison initially failed;
normalizing these aliases established that the effective host file and all named
volume mounts were unchanged. No storage correction was necessary.

## Runtime metadata and ingestion

| API | JSON `service` | `serviceVersion` | `environment` |
| --- | --- | --- | --- |
| User | `user-learning` | `0.0.1-SNAPSHOT` | `development` |
| Learning | `learning-api` | `0.0.1-SNAPSHOT` | `development` |
| JWKS | `jwks-service` | `0.0.1-SNAPSHOT` | `development` |

Post-recreation stdout checks parsed 475 User, 460 Learning and 462 JWKS JSON
records. All matching application records carried the expected metadata; duplicate
`SERVICE_NAME`/`SERVICE_VERSION`/`DEPLOYMENT_ENVIRONMENT` context fields were absent.
OTLP/exporter WARN/ERROR counts were zero. Collector error/flush-failure count
since recreation was also zero. These are observation-window checks, not an
indefinite availability guarantee.

Final backend queries were restricted to post-start records with the new version
and environment fields:

| Backend | User | Learning | JWKS |
| --- | --- | --- | --- |
| Loki | 10 matching recent records sampled; newest 6.5s old | 10 sampled; 9.1s | 10 sampled; 9.3s |
| OpenSearch | 482 matching post-start records; newest 7.5s old | 467 records; 9.2s | 469 records; 9.5s |

This verifies forwarding through the recreated Fluent Bit process into both
backends, rather than merely finding historical documents. Loki's `environment`
stream label also matched `development`. Grafana health remained OK.

## Live API verification

No matching saved Postman collection was found. Local Postman CLI **1.75.0** was
used for nine positive requests with **20 named `pm.test` checks**; remote event
reporting was disabled. Six additional negative HTTP checks used in-memory Python
requests with exact status assertions. Additional local assertions compared JWT
algorithm/key ID, token subject, Learning identity and returned User ID.

| Check | Expected / actual result |
| --- | --- |
| User, Learning, JWKS readiness | Each HTTP 200, `status=UP` |
| `/api/v1/jwks/user` | HTTP 200; RFC 7517 envelope and public RS256 key fields; cache contract unchanged |
| `/api/v1/jwks/learning` | Same guarantees for Learning's public keys |
| User `POST /auth/login` with supplied existing account | HTTP 200; Bearer access token, refresh token and positive expiration |
| Learning `GET /api/v1/learning/me` with login token | HTTP 200; authenticated subject matched login JWT |
| Learning `GET /api/v1/learning/internal-test/users/{id}` | HTTP 200; returned User ID matched authenticated subject; active account; no password-hash field |
| User `GET /internal/users/{id}` without token | HTTP 401 |
| Same internal route with the user access token | HTTP 401, confirming the service-token boundary |
| Learning `/me` without token | HTTP 401 |
| Learning `/me` with malformed token | HTTP 401 |
| Login for a generated nonexistent account | HTTP 401; no account created |
| JWKS unknown owner | HTTP 404 |
| User `POST /auth/logout` for verification refresh token | HTTP 200; verification refresh session revoked |

**Final result: 15 live checks passed.** All nine positive Postman commands exited
zero; all six negative status assertions passed. Success through Learning's internal
client together with rejection of the user token at User's internal route verifies
the real Learning service-JWT flow, not a mocked or bypassed endpoint.

One normal login refresh-session record was created and then revoked through the
API. No user account, password, role or activation state was altered, and no
existing sessions were revoked. Stateless access-token invalidation is not claimed.
Credentials and complete JWTs were not printed or written to files/reports.

## Failures and harness corrections

1. `postman request --help` initially failed inside the sandbox because the CLI
   could not read its managed Private Cloud registry manifest. Authorized execution
   outside the sandbox succeeded; no CLI configuration or installation was changed.
2. The initial Python wrapper expected the CLI stdout to contain only one JSON
   document. Appended runner output caused a parsing error on readiness. The wrapper
   was corrected to decode the first JSON document, with CLI assertion exit status
   still checked. No login session had been created by this failed attempt.
3. Postman `--body -` produced HTTP 400 `INVALID_REQUEST` on login, including a
   redacted diagnostic retry. Supplying JSON as an in-memory subprocess argument
   resolved it. These were request-harness failures; no application repair or
   credential change was required, and no successful sessions were created by them.
4. Literal collector mount comparison failed on Docker Desktop path spelling;
   normalized comparison passed as described above.

No deployment build, recreation, health or final authentication/ingestion check
failed. Dockerfile packaging skips test execution as already configured; the
previously passed 195 Phase 0 Maven tests were not rerun during this runtime-only
verification because no application source/configuration was changed here.

## Separate `japanese-learning` consumer review

Read-only review inspected its Compose configuration, .NET
`AuthenticationExtensions.cs`/`JwksConfigurationRetriever.cs`, and Quarkus OIDC
properties. Runtime environment inspection showed both consumers use
`http://jwks-api:8080/api/v1/jwks/user` on their own project network. They do not
point to this project's host port or containers.

Phase 0 modifies JWKS observability configuration, not its controller, owner
routes, RSA key schema/material or cache contract. The published contract also
matched the pre-deployment snapshot. **No breaking consumer compatibility issue
was identified; no change to `japanese-learning` was needed or made.**

Its JWKS submodule remained clean at
`53d50ba151d04d7ee7d4f7ea01beba524262c3d9`. Its .NET working tree remained clean;
pre-existing Angular and Quarkus changes remained present. No .NET/Quarkus builds,
container actions or live consumer-authentication tests were run. Compatibility
assessment therefore covers isolation and the unchanged JWKS contract, not a new
end-to-end login test of the other stack.

## Command record

The following commands/check blocks were actually executed. Credentials/tokens
are represented only by placeholders below; no secret-bearing command output is
included. In-memory Python blocks captured subprocess output before printing
allowlisted summaries.

### Inspection and validation

```powershell
git status --short
git -C <each Spring Boot module> status --short
git -C C:/Personal/japanese-learning status --short
git -C C:/Personal/japanese-learning/springboot-jwks-api status --short
git -C C:/Personal/japanese-learning/springboot-jwks-api rev-parse HEAD
git -C C:/Personal/japanese-learning/dotnet status --short
git -C C:/Personal/japanese-learning/quarkus status --short
git -C springboot-jwks-api diff -- src/main/java
docker compose ls --format json
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml config --quiet
docker compose -p springboot_project exec -T user-api sh -c 'command -v curl'
postman --version
postman request --help
python observability/verify-baseline.py --runtime
```

Read-only `Get-Content`, `Get-ChildItem`, `Get-Command` and scoped `rg` commands
inspected the API DTOs/controllers, User Dockerfile, debug override, baseline
verifier, existing SQL migrations, skill instructions, external repository
AGENTS/Compose/JWKS-consumer files, and available CLI/collection paths.

Snapshot/preservation Python blocks (`python -`) executed:

```text
docker ps -aq --filter label=com.docker.compose.project=springboot_project
docker ps -aq --filter label=com.docker.compose.project=jp_dev
docker inspect <selected existing container IDs>
docker inspect springboot_project-<API>-1
docker logs --since <that container's StartedAt> <container ID>
```

They hashed protected files without printing contents and compared public JWKS
responses. Temporary snapshot state contained container metadata, fingerprints
and public JWKS only; it was removed after verification.

### Deployment commands

```powershell
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml build user-api learning-api jwks-api
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build --wait --wait-timeout 120 jwks-api
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build --wait --wait-timeout 120 user-api learning-api
docker compose -p springboot_project --env-file .env -f docker-compose.yml -f docker-compose.debug.yml up -d --no-deps --no-build --wait --wait-timeout 60 fluent-bit
```

Builds completed before recreation. `--no-deps` prevented database, migration
runner or backend recreation; `--no-build` separated runtime application from
build work. No `--force-recreate`, `--remove-orphans` or `down` was used.

### API and backend checks

Positive requests used this local-only command pattern with endpoint-specific
assertions; login/logout bodies and bearer headers were supplied from memory:

```text
postman request <METHOD> <endpoint from the table above>
  --no-report-events --response-only --timeout 20000
  --script-post-request <HTTP and contract assertions>
  [-H Content-Type:application/json --body <in-memory JSON>]
  [-H Authorization:Bearer <in-memory token>]
```

The first two failed login attempts used `--body -` instead; a standalone health
formatting check used timeout 10000. Python in-memory HTTP checks performed the
six negative requests in the table and these read-only backend queries:

- Loki `/loki/api/v1/query_range`: post-start timestamp window, canonical service,
  `environment=development`, parsed `serviceVersion=0.0.1-SNAPSHOT`.
- OpenSearch `/springboot-<service>-logs/_search`: post-start timestamp and
  version/environment filters, latest record projected to non-sensitive metadata.
- Baseline verifier health, labels, freshness, mappings and Grafana health queries.

## Final limits and Git state

Phase 0 runtime deployment is verified. Full tracing, metrics storage, retention
deletion, outage durability, and authenticated Grafana datasource/UI checks remain
outside this verification. Existing OpenSearch yellow single-node status persists;
no cluster/index policy was changed. No unexpected exporter connection errors were
seen, but this does not prove a future OTLP destination works.

The existing Phase 0 root/submodule edits remain unstaged and uncommitted. This
verification adds this report and documentation links only; all three Spring Boot
submodule HEADs/branches are unchanged. No Git commit, push, reset, branch change,
secret rotation, user-account modification or unrelated repository edit occurred.
