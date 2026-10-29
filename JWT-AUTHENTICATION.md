# JWT authentication across services

User Service signs access tokens with its single active RSA private key (RS256).
JWKS Service independently publishes **all** configured public keys at
`/.well-known/jwks.json`, including inactive signing keys. Learning Service uses
Spring Security Resource Server and Nimbus to verify bearer tokens against that
independent endpoint. It does not call User Service during authentication and has
no key-file mounts. User Service's existing JWKS endpoint remains unchanged.

## Verification and authorization

`GET /api/v1/learning/me` accepts roles 1 (USER) and 2 (ADMIN). Spring Security
extracts the bearer token, verifies its signature using the trusted JWKS key
matching header `kid`, validates claims, and creates a `JwtAuthenticationToken`.
The controller only reads that authenticated principal and uses the existing
APIResponse envelope. No database lookup is needed.

Only RS256 is accepted. The configured issuer must match exactly; `exp`, `iat`,
`sub` and a nonblank `kid` are required. Expiration and optional `nbf` use the
configured clock skew; future `iat` beyond skew and `exp <= iat` are rejected.
User Service currently issues no audience or username, so neither is required or
returned. Audience validation should be added together with an issuing-contract
change if service-specific audiences are introduced.

Nimbus handles key selection, in-memory JWKS caching (framework default: five
minutes), and refresh on an unfamiliar `kid`. Authentication does not fetch keys
on every request. A cached matching key can validate during an outage while usable;
retrieval failures without a usable key return 401. Unknown keys never bypass
verification. See the [Spring Security reference](https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html).

Missing, malformed, expired, tampered, wrong-issuer and unverifiable tokens return
401 with the standard bearer challenge. Valid tokens without either supported
role return 403. These are Spring Security responses, outside controller advice.
Public health, Swagger, `/test`, and existing integration routes remain public.
The API uses stateless bearer authentication, with CSRF disabled and no session login.

## Configuration

| Variable | Purpose |
| --- | --- |
| `JWT_ISSUER` | Exact issuer used by User and trusted by Learning |
| `JWT_JWK_SET_URI` | Full independent JWKS endpoint for a locally launched Learning process |
| `LEARNING_JWT_JWK_SET_URI` | Optional Compose override; defaults to `http://jwks-api:8080/.well-known/jwks.json` |
| `JWT_CLOCK_SKEW` | Learning time tolerance, default `60s`; nonnegative duration |
| `JWKS_SERVICE_BASE_URL` | Existing public-key diagnostic client's base URL |
| `JWKS_SERVICE_GET_PUBLIC_KEYS` | Existing client's endpoint path |

No issuer discovery is performed. Production JWT URL and issuer configuration is
required; local addresses below are examples only. Compose supplies internal DNS
addresses; do not use host loopback addresses between containers.

The root `.env` configures User's indexed `APP_SECURITY_JWKS_KEYS_*` settings;
`jwks-keys.env` configures JWKS Service's corresponding key IDs and paths. Both
currently mount `./key` read-only and validate matching private/public pairs at
startup. **JWKS currently requires private keys even though it exposes only public
components.** A public-key-only loader is a separate hardening opportunity; this
implementation preserves the existing key distribution. Never copy keys into Learning.

## Local development (PowerShell)

Run JWKS and User with their existing key configuration and databases first.
For Learning, point its datasource variables at the local PostgreSQL instance,
then set (using the ports currently configured in the root `.env`):

```powershell
$env:JWT_ISSUER='japaneselearning-user-service'
$env:JWT_JWK_SET_URI='http://127.0.0.1:8781/.well-known/jwks.json'
$env:JWKS_SERVICE_BASE_URL='http://127.0.0.1:8781'
$env:JWKS_SERVICE_GET_PUBLIC_KEYS='/.well-known/jwks.json'
$env:SERVER_PORT='8783'
cd springboot-learning-api
./mvnw.cmd spring-boot:run
```

## Docker and example requests

From the root:

```sh
docker compose config --quiet
docker compose up -d --build user-api jwks-api learning-api
```

Compose retains existing databases, migrations, ports and key mounts. Learning can
start without contacting JWKS; its first authenticated request needs JWKS or a
usable cached key. Existing `.env` host ports are User 8782, JWKS 8781, Learning 8783;
check your own overrides before using these examples. Container traffic uses 8080.

```sh
curl -X POST http://127.0.0.1:8782/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"usernameOrEmail":"your-user","password":"your-password"}'
# Copy data.accessToken into TOKEN without sharing or logging it.
curl http://127.0.0.1:8783/api/v1/learning/me -H "Authorization: Bearer $TOKEN"
curl -i http://127.0.0.1:8783/api/v1/learning/me
curl -i http://127.0.0.1:8783/api/v1/learning/me -H 'Authorization: Bearer invalid'
```

Successful response (metadata values vary):

```json
{"success":true,"data":{"userId":"42","authorities":["ROLE_USER","FACTOR_BEARER"],"issuer":"japaneselearning-user-service"},"meta":{"timestamp":"...","correlationId":"..."}}
```

The last two requests return 401. A correctly signed token with a missing or
unsupported role returns 403. Changing a role in an existing token invalidates its
signature and returns 401, not 403.

## Rotation

1. Generate a new RSA pair and assign a new unique `kid`; do not reuse a key ID.
2. Add the new pair to existing key configuration. Publish it in JWKS before User
   starts signing with it. Providers load files at startup, so recreate/restart
   the affected service after changing configuration.
3. Keep exactly one User signing key active; switch it to the new key. The JWKS
   provider also currently requires exactly one active flag but publishes every key.
4. Retain old verification keys until every token they signed has expired, including
   clock skew. Learning refreshes for the new `kid` and continues accepting old tokens.
5. Remove retired keys later. Cached keys can remain trusted until cache refresh;
   removal is not instantaneous revocation. Logout/refresh-token revocation does
   not revoke already issued access tokens in Learning.

## Automated verification

Run `./mvnw.cmd -B -ntp test` inside each submodule. Learning's tests generate RSA
keys in memory and use a local HTTP JWKS server with the actual Nimbus decoder and
Spring Security filter chain. They cover both signing keys, rotation refresh,
cache reuse/outages, roles, 401/403, signature/payload tampering, issuer, algorithm,
required claims, expiration, nbf, future iat and clock skew. No production keys are
used by tests. Existing User/JWKS tests remain unchanged.

## Verification performed for this change

- Learning: 24 tests passed (22 JWT integration/cache tests and 2 existing tests).
- User: 26 existing tests passed.
- JWKS: 31 tests passed; the existing `LoggingConfigurationTest` failed because
  its full application context supplies no RSA configuration (`At least one RSA
  key must be configured`). No JWKS source files were changed.
- `docker compose config --quiet` and the Learning Docker image build passed.
- Live Docker registration/login through User followed by `/api/v1/learning/me`
  succeeded with ROLE_USER and the framework's FACTOR_BEARER authority. Missing
  and malformed bearer tokens returned 401. The independent JWKS exposed both
  `user-rsa-v1` and `user-rsa-v2`; Learning's runtime URL was the `jwks-api` DNS
  endpoint and its only volume mount was the log directory.
- Live smoke testing created account `jwt-smoke-9a3832331f58` in the local User
  database. Its randomly generated password was not retained. No existing users
  or databases were modified or migrated.
- Both-key verification and rotation were exercised with generated test keys;
  the live smoke test used User's currently active signing key without changing
  deployment key configuration.
