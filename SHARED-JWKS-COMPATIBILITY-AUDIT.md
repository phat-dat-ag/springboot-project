# Shared JWKS compatibility audit

Audit date: 2026-11-16. Requested D: repositories do not exist on this machine;
all work used C:\Personal\springboot-project as the command working root and
C:\Personal\japanese-learning as an inspection-only reference.

## Result

Spring Boot remains compatible with the inspected JWKS implementation at
852f3d6dd5dbd74dce06343525f3c953df04f2ef for its existing owner-scoped
publication and JWT flows. No runtime-code regression was introduced between
Spring Boot's recorded JWKS revision and that checkout: the entire intervening
Git diff changes only JWKS .env.example and README.md. Source security tests,
three module builds, resolved configuration, and read-only checks of the existing
running services support this result. This is not certification that freshly
built images have been deployed, or that all Japanese Learning flows work.

No source, Dockerfile, Compose, issuer, key, credential, real environment file,
submodule pointer, observability pipeline, or runtime deployment was changed.
The only remediation is documenting optional User JWKS caller identity overrides
in .env.user-api.example, plus this report and its link in JWT-AUTHENTICATION.md.
These fields are diagnostic metadata, never authenticated caller identities.

## Git state and preservation

| Repository | Branch | HEAD | Parent recorded pointer / initial changes |
| --- | --- | --- | --- |
| Spring Boot root | develop | ceda8626b81c1f5d8a74ae0cd5ff9c01985d1187 | Only initial modification: JWKS pointer mismatch |
| springboot-user-api | develop | 309d68ea299368d939f3b4083dbd44c3537fa0d8 | Same pointer; clean |
| springboot-learning-api | develop | 8cb37c6bb66ee453316f0f3ecbf8af5e9ba63309 | Same pointer; clean |
| Spring Boot springboot-jwks-api | develop | 852f3d6dd5dbd74dce06343525f3c953df04f2ef | Root records e9b90c31dfa311e0121285c8b7caa37c09cf4287; child clean |
| Japanese Learning root | develop | 8498c64a37be334a661eda572c4893fcc46bd0bc | Pre-existing modified Quarkus child |
| Japanese Learning springboot-jwks-api | develop | 852f3d6dd5dbd74dce06343525f3c953df04f2ef | Same pointer; child clean |
| Japanese Learning dotnet | detached HEAD | ee9cf906751639c7b45dc51dcfa9b1869103d2b2 | Clean |
| Japanese Learning quarkus | detached HEAD | d3293e0dc1b2a99715a5ef0b1983c6db46a2826f | Pre-existing src/main/resources/application.properties modification |
| Japanese Learning angular (revision inventory) | not audited | 33c99f69aff663fccf03b34d90eccb33c3e4f3b6 | Not modified |

Spring Boot .gitmodules defines paths springboot-user-api,
springboot-learning-api and springboot-jwks-api with respective URLs
https://github.com/phat-dat-ag/springboot-user-api.git,
https://github.com/phat-dat-ag/springboot-learning-api.git and
https://github.com/phat-dat-ag/springboot-jwks-api.git. Learning tracks develop;
User and JWKS have no branch entry. Japanese Learning's JWKS path/URL match,
with branch=develop. Its other children are dotnet, quarkus and angular at
https://github.com/phat-dat-ag/japanese-learning-{dotnet,quarkus,angular}.git.

The JWKS copies have separate Git directories: Spring Boot uses the child's
.git directory; Japanese Learning uses .git/modules/springboot-jwks-api.
They are not a single shared working tree. A local edit to one does not edit the
other. Their matching checked-out commit contains the recent committed template
change cfcd396 and merge 852f3d6; no uncommitted JWKS edits were found.
No fetch/pull was performed, so remote freshness is unverified.
No synchronization is needed for this compatibility result; the existing parent
pointer mismatch is intentionally excluded from the proposed commit.

## Publication and trust contracts

| Consumer | Key source | Verification and compatibility |
| --- | --- | --- |
| Spring User external decoder | /api/v1/jwks/user | RS256, configured issuer, Spring default timestamp validators; numeric role 1/2 maps to USER/ADMIN |
| Spring Learning inbound decoder | /api/v1/jwks/user | RS256, issuer, timestamps and explicit nonblank kid/sub, required iat/exp, future-iat tolerance and exp-after-iat |
| Spring User internal decoder | /api/v1/jwks/learning | RS256, exact internal+jwt, kid/jti, configured issuer/subject/audience, required iat/exp, skew and bounded lifetime |
| Spring Learning diagnostic client | /api/v1/jwks/user | Parses unwrapped keys into PublicKeysResponse; not an authentication mechanism |
| Japanese .NET User | /api/v1/jwks/user | JwksConfigurationRetriever parses JsonWebKeySet directly; issuer/audience/lifetime/signature/RS256 validation, no OIDC discovery |
| Japanese Quarkus | /api/v1/jwks/user | OIDC discovery/introspection disabled; RS256, issuer/audience, subject required; iat deliberately optional for .NET tokens |
| Japanese nginx gateway | No independent JWT/JWKS decoder found | Forwards Authorization; authorization remains with upstream APIs |

JWKS has exactly one owner-path GET mapping, /api/v1/jwks/{owner}, supporting
lowercase user and learning. Owner selection is not a query parameter. Responses
are unwrapped {"keys":[...]}; each key has kty,use,alg,kid,n,e and nothing private.
Keys are RSA signature keys with alg=RS256; modulus/exponent use unsigned base64url.
Responses are public-cacheable for 300 seconds. Unknown/missing owners return
404. A supported owner with no configured keys returns 200 and an empty array:
Japanese Learning's learning owner currently does this. A query does not replace
the required owner path. Legacy well-known URLs are not supported routes.

Configuration requires explicit USER/LEARNING ownership and unique nonblank kids;
missing owners, duplicates, bad PEMs or missing files fail loading. Only public
X.509 PEM files are mounted into JWKS, individually read-only. Signing services
receive their own PKCS#8 private files. The owner filter selects keys by configured
ownership, not token-supplied identity or inferred filenames. Cache refresh/rotation
must account for both the server cache header and consumer library caches.

User signs its own JWTs with kid, issuer, subject, iat, exp, jti and numeric role.
Learning verifies them and separately signs short-lived internal service tokens;
its User client attaches a fresh service token, not the incoming user bearer.
User uses a first /internal/** security chain, grants SERVICE_LEARNING after
identity validation, permits the explicit GET lookup, and denies other internal
operations. Its external chain protects admin routes with ADMIN. Learning protects
learning routes with USER/ADMIN and leaves the existing public diagnostic route.
The internal lookup grants service access, not end-user ownership checks.

Spring external tokens intentionally have no audience claim/validation in the
current contract. Do not add Japanese Learning's audience or issuer to make the
two products accept each other's tokens. User's external decoder does not explicitly
require kid/sub/iat/exp or validate future iat/exp ordering as Learning does; default
library validation is not evidence that every missing-claim case is rejected.
This is a pre-existing validation-policy difference, not introduced by the two
JWKS commits. Exhaustive malformed-claim runtime acceptance at User is unverified;
no acceptance rule was silently changed during this compatibility audit.

### Compatibility classification

- Backward-compatible: 852f3d6 versus e9b90c3 runtime code/configuration; public
  response shape, owner routes, signing algorithms and observability code unchanged.
- Conditionally compatible: copying the new standalone JWKS .env.example requires
  filling now-blank public paths. Spring does not load .env automatically. Root
  Compose uses .env.jwks-api instead, so existing Spring Boot deployment is unaffected.
- Conditionally compatible: .NET and Quarkus consume the same publication format,
  but require their own User keys, issuer and audience. Runtime key sets were
  verified distinct from Spring User and Spring Learning.
- Breaking if attempted: pointing Spring consumers at Japanese Learning's JWKS,
  publishing all owners together, removing owner paths, mixing keys, changing
  issuer/audience, or feeding .NET tokens without iat to Spring Learning. None done.
- Unverified: authenticated .NET/Quarkus and gateway end-to-end flows against rebuilt
  images. Their source contracts were inspected; tests were not run in that repo.

No optional owner-specific Spring Boot consumer overlay exists in the inspected
tracked files or root inventory. Current owner URLs are directly in the base
Compose file. Running Spring API container labels list only docker-compose.yml;
there is no evidence of such an overlay being active. The separate secure-production
observability overlay exists but is unrelated and remains inactive. No overlay
was created or activated to reconcile a historical assumption.

## Configuration, containers and observability

Root .env is Compose interpolation input; .env.user-api, .env.learning-api and
.env.jwks-api are container env_file sources. Explicit environment entries override
env_file values; shell interpolation overrides .env. Required database credentials,
JWT issuer and Grafana initial credentials use required interpolation rather than
secret defaults. All variables referenced by the base/debug Compose interpolation
were found in the root example; current required fields are populated. The template
addition documents optional User caller metadata only; no real .env edits were needed.
Current configured signing/public paths all resolve to existing individual PEM mounts
(User 2, Learning 1, JWKS 3). No keys were printed, replaced, copied into examples,
or rotated. Existing issuer/lifetime values were preserved.

Base and debug Compose validation passed without starting anything. Build contexts,
8080 container listeners, readiness URLs, database migration dependencies, persistent
volumes and private 9091 scrape ports align. APIs use read-only containers with explicit
log volumes and tmpfs; named volumes are project-scoped. No fixed container_name,
external network, external volume, Japanese env-file path or Japanese bind source
was found in Spring's resolved base. The inspected running API networks are
springboot_project_default versus jp_dev_default; JWKS mount sources and log volumes
are separate. Japanese shared-provider/consumer overlays share its observability
networks only; Spring base does not join them. Separate project names alone would
not protect manually shared ports, names, paths or external networks.

Current Spring loopback ports: User 8781, Learning 8782, JWKS 8783, MySQL 3336,
Postgres 5433, Prometheus 9090, Grafana 3077, Loki 3177, OpenSearch 9277 and
Dashboards 5677. Japanese runtime uses User 8081, vocabulary 8082, JWKS 8083,
gateway 8880, frontend 8099, Prometheus 9091 and Grafana 3001. No observed collision.
The Spring example/default Learning port 8081 conflicts with Japanese User's
current port. The examples also default Spring User and Japanese gateway to 8080.
Keep existing local port choices; choose unused ports before deploying examples
side by side. No deployment redesign or automatic port renumbering was warranted.

Spring already uses Loki AND OpenSearch for logs; Loki was not introduced here.
JSON encoders restrict metadata/MDC/key-value fields, sanitize messages and stack
traces, and omit raw bodies, auth headers and token values. Correlation filters run
before security, sanitize caller metadata, and clear MDC. Tests cover these boundaries.
Service identity remains user-learning, learning-api and jwks-service, with
development labels in the inspected deployment. Instrumented Boot HTTP builders
preserve client observations; User-client connect/read timeouts and internal JWT
interceptor remain in place. W3C trace propagation, no baggage, privacy-filtered
span export and the existing Collector -> Tempo pipeline were preserved.

Prometheus exposes no API scrape port on the host; public /actuator/prometheus
returns 403 on all APIs. Nine live scrape targets were up. Fluent Bit retains
application_json parsing, stable-name/spool tail paths, persistent offsets and
bounded per-output queues. Grafana datasource URLs still point to internal Loki,
Prometheus and Tempo; its health endpoint reported database=ok. OpenSearch returned
yellow, timed_out=false, one node; this is not a green-cluster or backup guarantee.
Recent sampled application records parsed as JSON with expected identities:
User 66, Learning 54, JWKS 66; zero non-JSON lines in those sampled outputs.
This sample does not prove end-to-end log delivery or complete sensitive-data absence.

Existing budgets remain: application spool 100MB/30-history/2GB defaults, Docker
rotation 10m x3, Fluent Bit 64M Loki and 32M per OpenSearch output, persistent
Collector queue 67108864 bytes, Prometheus 15d/2GB and Tempo 72h. OpenSearch lifecycle
installation is an existing explicit tool, not automatic evidence of live retention.
Backup/restore documentation still states recovery/RPO/RTO are not verified. Secure
production overlay startup/TLS/authorization acceptance remains separate and unverified.
No historical acceptance results were overwritten or reasserted as new tests.

## Validation executed

All module commands used installed Java 21 at
C:\Users\DatNguyen\.jdks\ms-21.0.12.1 and mvn -B -ntp -o verify. Initial PATH Java
was 17; no system settings were changed. User/JWKS POM Java targets remain 17 and
Learning retains its configured target; Java 21 execution is not a target migration.

| Validation | PASS | FAIL | Errors | Skipped |
| --- | ---: | ---: | ---: | ---: |
| User Surefire tests | 105 | 0 | 0 | 0 |
| Learning Surefire tests | 121 | 0 | 0 | 0 |
| JWKS Surefire tests | 83 | 0 | 0 | 0 |
| Total automated module tests | 309 | 0 | 0 | 0 |
| Maven verify/package builds | 3 | 0 | 0 | 0 |
| Base/debug Compose config --quiet | 2 | 0 | 0 | 0 |
| Live public endpoint/security/key-separation assertions | 22 | 0 | 0 | 0 |
| Live signed JWT flow assertions | 6 | 0 | 0 | 0 |

Surefire XML counts were summed from each module target/surefire-reports after
successful builds. Existing suites include owner-isolation/RSA/provider contract,
User/internal and Learning JWT/security, client authentication/timeout handling,
structured logging/privacy, metrics listener/client/security and tracing integration.
No tests were disabled or weakened. No database container/deployment was created.

The 22 live assertions covered four owner responses (including empty Japanese
learning), response fields/algorithms/kids, cache headers, key-material separation,
unknown/missing-owner 404s, three readiness successes, three public-metrics 403s,
and two protected routes returning 401 without credentials.

Six live JWT assertions used ephemeral tokens signed locally with existing matching
keys, never printed or persisted. A random subject/lookup UUID avoided existing user
data. Learning /me accepted a correctly signed User token (200); User admin lookup
accepted it through authentication and returned absent-record 404. Learning internal
identity passed User internal authentication and returned absent-record 404. A Learning
key signing a forged external-User identity was rejected at both APIs (401); a User
token was rejected at User's internal chain (401). All calls were GET; no accounts,
activation, refresh sessions or persistent application data were changed. Normal
request logs/metrics are expected side effects. The temporary Java signer initially
failed compilation due to PowerShell's UTF-8 BOM; removing the BOM fixed the harness
before runtime assertions ran. This was not a project build/test failure.

Additional read-only observations: Docker names/ports, selected nonsecret inspect
metadata/mounts/networks, User curl availability and UID (curl exists; UID=0), nine
Prometheus targets, Grafana/OpenSearch health, and bounded JSON log samples.
A suspected missing-curl Dockerfile problem was disproved against the running image;
no speculative Dockerfile fix was made. User's root runtime UID is pre-existing;
changing it would require log-volume/key-permission migration review, outside this
compatibility correction. Existing images are not proved to equal today's source.

Not performed: rebuilding/replacing container images, restarting/stopping/removing
containers, isolated stacks, DB migration reruns, authenticated Japanese application
flows, key rotation/cache-expiry rehearsal, fresh trace-to-Tempo or log-to-OpenSearch
acceptance, secure-overlay rollout, restore/retention acceptance, or full malformed
claim runtime matrices. Existing historical reports are references, not new runtime
proof. No full cross-repository runtime compatibility claim is made.

## Changes, remaining risks and review commands

Changes by service: User template documents three optional JWKS_CALLER_* fields;
Learning and JWKS source/config unchanged. Root documentation links this report.
Environment-value changes: none. Compose changes: none. Observability changes: none.
Updated Markdown: SHARED-JWKS-COMPATIBILITY-AUDIT.md and JWT-AUTHENTICATION.md.
No Java files changed; no Java formatting churn. Existing R01-R19 instructions
were inspected and their style document was read before considering source changes.

No coordinated Japanese Learning fix is required by the inspected JWKS delta.
Any future shared endpoint/ownership/issuer change requires coordinated consumer
review before implementation. Runtime rollout, shared networks/ports, key/issuer
changes, optional overlay activation and backup operations remain unapproved and
were not attempted. Remote branch freshness, deployed-image provenance and the
unexecuted scenarios above are the exact limits of this assessment.

Only Spring Boot root has task changes. The proposed docs/shared-jwks-compatibility-audit
branch was checked absent locally; the root's staged index was empty. Final commands
must stage only the three task files, exclude the pre-existing JWKS gitlink mismatch,
and exclude all secrets/runtime outputs. No child repository commands are justified.
No branches, staging, commits or pushes were executed.
