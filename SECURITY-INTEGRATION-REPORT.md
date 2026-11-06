# Unified JWKS and Internal JWT implementation report

Completed 2026-11-06. No Git branch, staging, commit, push, reset or destructive operation was executed.

## Architecture and API

One public JWKS mapping, `GET /api/v1/jwks/{owner}`, supports lowercase `user` and `learning`.
Each endpoint returns only its explicitly configured owner group in standard unwrapped JWK format.
Unknown/missing owners return 404, never an all-keys fallback. Cache-Control remains max-age=300,
public. Retired well-known routes have no compatibility mapping; every in-project application
consumer was migrated. Root JWT-AUTHENTICATION.md documents the full contract and variable table.

Explicit OWNER=USER/LEARNING is mandatory. Missing/invalid owners, malformed files and duplicate
IDs fail startup. Multiple retained public keys per owner are supported. Ownership is not inferred
from names. JWKS does not select a signing key or enforce an active count. User and Learning's
existing exactly-one-active private signing key requirements remain unchanged.

User external JWT validation and Learning inbound JWT validation trust only `/api/v1/jwks/user`.
User has an ordered `/internal/**` chain whose separately qualified decoder trusts only
`/api/v1/jwks/learning`. It enforces RS256, nonblank kid and jti, exact internal+jwt type,
configured issuer/subject learning-service, audience user-service, required iat/exp, optional nbf,
5-second skew and maximum issued lifetime of 300 seconds. Nimbus's default type check is disabled
only on that decoder and replaced by explicit exact type validation; external type handling is
unchanged. JWTs never determine their own trusted JWKS URL.

Only the validated service identity receives SERVICE_LEARNING. GET /internal/users/* requires
that authority; other internal routes/methods are denied. User/Admin authorities remain external.
Invalid/missing credentials and cross-token use return 401; authenticated route-policy denial
returns 403. The business lookup and response contract are unchanged.

Learning reuses its existing dedicated signer and per-request bearer attachment. Compose now
enables attachment, which replaces rather than forwards incoming user credentials. JWKS clients
receive no Internal JWT. Existing timeouts, response mapping and safe error handling are retained.

## Files changed and reasons

### User

- New config/InternalJwtSecurityProperties.java: validated, independent internal trust/time settings.
- New config/InternalJwtDecoderConfig.java: strict RS256 internal decoder using the Learning key source.
- config/SecurityConfig.java: ordered and explicitly qualified external/internal security chains.
- config/JwtDecoderConfig.java: retain the existing external decoder as primary; no global replacement.
- application.properties: internal settings and canonical PRIVATEKEYPATH with first-key legacy fallback.
- New config/InternalJwtAuthenticationTest.java: real signed JWTs, HTTP JWKS fixtures, decoders and chains.
- Existing decoder/controller tests: new URL, service authentication and preserved external role checks.
- JWT.md and .env.example: synchronize trust separation, mount rules and environment names.

### JWKS

- config/RsaKeyProperties.java and security/RsaKeyProvider.java: explicit enum ownership and fail-closed loading.
- service/JwksService.java: owner-only filtering with no unscoped publishing method.
- controller/JwksController.java: one parameterized mapping and controlled unknown-owner 404.
- config/SecurityConfig.java: public GET access for the new API; unrelated access rules retained.
- application.properties and .env.example: canonical indexed public-key variables and required owners.
- Provider/logging tests and new controller/JwksEndpointsTest.java: isolation, binding, error and HTTP contracts.
- README.md, LOGGING.md and docs/INTEGRATION.md: all consumer URLs and current configuration synchronized.

### Learning

- application.properties: clarify authenticated User-client behavior; inbound trust policy preserved.
- Test properties: user-owner JWKS URI.
- JwtAuthenticationTest.java: existing authority checks now test membership instead of nondeterministic array order.
- .env.example and INTERNAL-JWT.md: current URLs, signer/client settings, mounts and verification behavior.
- Existing signer, signing-key loader, HTTP client and DTO/business implementation reused without refactoring.

### Root

- docker-compose.yml: new trusted decoder URLs/settings; enable outbound JWT; individual read-only key mounts.
- .env.example, .env.user-api.example, .env.jwks-api.example: deployment settings and canonical indexed names.
- JWT-AUTHENTICATION.md: current architecture, environment table, key layout, deployment and rotation guidance.
- This report: validation evidence, limitations and exact manual Git delivery commands.
- Local Git-ignored environment changes are listed separately below; do not stage them.

## Environment audit

Eight root environment files exist; all were reviewed. Only docker-compose.yml references service env files.
No additional Compose files were found. Database credentials, ports, logging, observability and persistent
volume settings were preserved. No real secret was replaced with a placeholder.

| Root file | Disposition |
| --- | --- |
| .env | Migrated existing URLs; added missing nonsecret trusted-internal and signer/client defaults; explicitly enabled outbound attachment |
| .env.example | New internal decoder variables, unified consumer URLs, enabled attachment and file-mount descriptions |
| .env.user-api | Canonicalized existing PRIVATE_KEY_PATH names to PRIVATEKEYPATH, preserving IDs, paths and active selection |
| .env.user-api.example | Canonical indexed private-key spelling |
| .env.jwks-api | Canonical PUBLICKEYPATH, required explicit owners, preserved User entries and Learning entry; removed obsolete ACTIVE settings |
| .env.jwks-api.example | Matching public-only owner configuration |
| .env.learning-api | Reviewed and unchanged: dedicated Learning key ID/path/active settings already correct |
| .env.learning-api.example | Reviewed and unchanged: indexed signer settings already correct |

Standalone examples in all three submodules were also synchronized. User's separate local .env was
reviewed and left unchanged because it is not consumed by root Compose; Java does not automatically
load .env files. Local users should export the standalone .env.example settings explicitly.

### Variables added or updated

- User external: USER_JWT_JWK_SET_URI maps to JWT_JWK_SET_URI and app.security.jwt.jwk-set-uri,
  now http://jwks-api:8080/api/v1/jwks/user. Existing JWT_ISSUER and token lifetimes are preserved.
- User internal (new): INTERNAL_JWT_JWK_SET_URI=http://jwks-api:8080/api/v1/jwks/learning,
  INTERNAL_JWT_ISSUER=learning-service, INTERNAL_JWT_SUBJECT=learning-service,
  INTERNAL_JWT_AUDIENCE=user-service, INTERNAL_JWT_CLOCK_SKEW=5s,
  INTERNAL_JWT_MAX_LIFETIME=300s. They bind to app.security.internal-jwt.*.
- User signing: APP_SECURITY_SIGNING_KEYS_<n>_PRIVATEKEYPATH replaces the noncanonical spelling;
  KID and ACTIVE values remain unchanged. The first-key legacy property fallback is retained.
- Learning inbound: LEARNING_JWT_JWK_SET_URI maps to JWT_JWK_SET_URI and the User owner URL.
  JWKS_SERVICE_GET_PUBLIC_KEYS is /api/v1/jwks/user. JWKS_SERVICE_BASE_URL remains Docker DNS.
- Learning outbound: USER_SERVICE_INTERNAL_JWT_ENABLED=true; existing USER_SERVICE_BASE_URL,
  GET_USER and timeouts are preserved/explicitly documented with internal User DNS and paths.
- Learning signing: LEARNING_INTERNAL_JWT_ENABLED=true, ISSUER=learning-service,
  AUDIENCE=user-service, TTL=60s (using the full LEARNING_INTERNAL_JWT_* names). Existing
  APP_SECURITY_SIGNING_KEYS_<n>_KID/PRIVATEKEYPATH/ACTIVE remain dedicated to Learning.
- JWKS: APP_SECURITY_JWKS_KEYS_<n>_KID/PUBLICKEYPATH/OWNER; owners USER for User v1/v2 and
  LEARNING for learning-rsa-v1. Obsolete JWKS ACTIVE entries removed; no private-path setting exists.
- Algorithm RS256 and type internal+jwt are fixed profile constants, not runtime bypass switches.
- USER_SIGNING_KEYS_DIR, JWKS_KEYS_DIR and LEARNING_SIGNING_KEYS_DIR retain their existing source locations.

## Final RSA layout and mounts

```text
key/
  userservice-private-v1.pem
  userservice-private-v2.pem
  userservice-public-v1.pem
  userservice-public-v2.pem
data/keys/learning/
  learningservice-private-v1.pem
  learningservice-public-v1.pem
springboot-user-api/keys/
  existing legacy copies of the four User PEM files (unmounted, unchanged, Git-ignored)
```

No key was moved, copied, regenerated or renamed. The existing legacy User public copies match
the root files. Runtime source-of-truth locations are the root directories above.

- User: only its private v1/v2 files mounted under /run/keys/jwt.
- Learning: only its private v1 file mounted under /run/keys/learning.
- JWKS: only User public v1/v2 and Learning public v1 files mounted under corresponding paths.
- Every key mount is read-only and uses create_host_path=false. JWKS has no private-key or
  signing-directory mount. Existing database/log volumes, ports and health checks remain intact.
- Future rotation requires explicit additional file mounts and matching indexed configuration.

## Automated validation

All affected services passed mvnw.cmd -B -ntp verify (compilation, tests and executable JAR packaging):

| Service | Tests | Failures/errors |
| --- | --- | --- |
| User | 61 | 0 |
| JWKS | 52 | 0 |
| Learning | 76 | 0 |

User's new real-decoder tests include valid Learning identity, missing credentials, expiry,
invalid signature, unknown/missing kid, wrong issuer/audience/type/subject, missing required claims,
future iat/nbf, excessive/inverted lifetimes, wrong algorithm, cross-key-set issuer spoofing,
User-token/internal-token separation, existing User/Admin roles, and valid-identity route denial.
JWKS tests cover owner isolation, missing/invalid ownership, duplicates, multiple keys, exact
public RSA components, response fields, public cache headers and controlled unknown/missing owner.
Learning's existing signing/attachment/isolation/error/timeout and user JWT tests all pass.

Initial test-slice wiring needed a test-only RestTemplateBuilder, which was fixed; final runs above
are clean. Postman CLI validation is unavailable because its managed Private Cloud manifest cannot be read; Maven and live HTTP verification were used. No dependencies were added. Docker builds also passed. Compose resolution and Git
whitespace checks passed. No old JWKS URLs remain in active source/configuration consumers.

## Runtime verification actually performed

Only jwks-api, user-api and learning-api were rebuilt/recreated using --no-deps. All three are
healthy. Databases, migrations, observability containers and persistent volumes were not recreated.
Docker mount inspection confirmed the private/public separation stated above.

Live checks passed:

- /api/v1/jwks/user: 200, exactly user-rsa-v1 and user-rsa-v2.
- /api/v1/jwks/learning: 200, exactly learning-rsa-v1.
- Every published modulus matches its configured public PEM; only standard public fields appear.
- Unknown/missing owner: 404.
- Learning public-key diagnostic client: 200 and only User v1/v2 keys, using the migrated URL.
- Real User registration/login and authenticated logout: successful.
- Admin user lookup: 200; ordinary User token on Admin route: 403.
- Real User JWT accepted by Learning /api/v1/learning/me: 200.
- Anonymous internal request: 401; User JWT on internal endpoint: 401.
- Valid Learning JWT on internal endpoint: 200; Learning JWT on external Admin endpoint: 401.
- Valid Learning identity on an unauthorized internal route: 403.
- Learning diagnostic user lookup, using real login token inbound and generated Internal JWT
  outbound: 200 with the expected user ID.

The first probe incorrectly attempted activation of an already-active new account and received
409. The probe was corrected to honor existing registration behavior; no business code changed.
Two synthetic smoke-test accounts remain in the local database, IDs:
1610512e-af2a-4ab7-be49-865bff7b769a and b0810048-1914-4224-9f1f-9cf4edc0e257.
Passwords and complete JWTs stayed in process memory and were not retained. The second account's
refresh token was revoked through real logout. Existing users were not altered. Optional cleanup
of these fixture accounts should follow the project's normal deliberate data-maintenance process.
The ignored data/security-runtime-results.json stores only statuses/fixture ID, not credentials.

## Remaining considerations and manual updates

- Current local deployment is updated; no further local configuration step is required.
- Other environments must migrate all owner URLs and canonical indexed names and add OWNER for
  every JWKS entry before deploying. Apply submodule commits before recording root pointers.
- Existing consumers outside this project must migrate; legacy endpoints are deliberately removed.
- Production bearer transport needs trusted networking/TLS. jti is not a replay cache, and token
  revocation is bounded by expiry and key-cache policy. Internal lifetime remains short by default.
- Ownership is trusted operator configuration; access to configuration/private keys must be controlled.
- Host-side legacy private copies were intentionally preserved. They are unmounted and ignored,
  but can be removed separately only through an explicitly reviewed key-retention decision.
- Dockerfiles require no change: they copy application source/JARs, not key files. Existing runtime
  Java versions and Spring versions were retained.
- Never commit real .env files, PEM/private keys, data/, test passwords, complete JWTs or runtime logs.
  In particular exclude root .env, .env.user-api, .env.jwks-api, .env.learning-api and User's local .env.
  Existing ignore rules cover them; tracked .example files contain no secrets.

## Exact Windows CMD Git delivery

No commands below were executed. Current staged sets were empty. Review staged diffs before
committing. Stop if any command fails. All initial submodule working trees were clean; root
configuration/pointer changes already present at task start were relevant and preserved.
Run the submodule blocks first, then root; never use git add . or stage real key/env files.

### springboot-jwks-api

```cmd
cd /d C:\Personal\springboot-project\springboot-jwks-api
git status --short
git switch -c feat/unified-owner-jwks
git add .env.example
git add LOGGING.md
git add README.md
git add docs/INTEGRATION.md
git add src/main/java/com/japaneselearning/jwks/config/RsaKeyProperties.java
git add src/main/java/com/japaneselearning/jwks/config/SecurityConfig.java
git add src/main/java/com/japaneselearning/jwks/controller/JwksController.java
git add src/main/java/com/japaneselearning/jwks/security/RsaKeyProvider.java
git add src/main/java/com/japaneselearning/jwks/service/JwksService.java
git add src/main/resources/application.properties
git add src/test/java/com/japaneselearning/jwks/controller/JwksEndpointsTest.java
git add src/test/java/com/japaneselearning/jwks/logging/LoggingConfigurationTest.java
git add src/test/java/com/japaneselearning/jwks/security/RsaKeyProviderTest.java
git diff --cached --stat
git commit -m "feat(jwks): publish isolated owner key sets through unified API"
git push -u origin feat/unified-owner-jwks
```

### springboot-user-api

```cmd
cd /d C:\Personal\springboot-project\springboot-user-api
git status --short
git switch -c feat/internal-jwt-authentication
git add .env.example
git add JWT.md
git add src/main/java/com/japaneselearning/user/config/InternalJwtDecoderConfig.java
git add src/main/java/com/japaneselearning/user/config/InternalJwtSecurityProperties.java
git add src/main/java/com/japaneselearning/user/config/JwtDecoderConfig.java
git add src/main/java/com/japaneselearning/user/config/SecurityConfig.java
git add src/main/resources/application.properties
git add src/test/java/com/japaneselearning/user/config/InternalJwtAuthenticationTest.java
git add src/test/java/com/japaneselearning/user/config/JwtDecoderConfigTest.java
git add src/test/java/com/japaneselearning/user/controller/internal/InternalUserControllerTest.java
git diff --cached --stat
git commit -m "feat(user): isolate Internal JWT authentication from user tokens"
git push -u origin feat/internal-jwt-authentication
```

### springboot-learning-api

```cmd
cd /d C:\Personal\springboot-project\springboot-learning-api
git status --short
git switch -c feat/authenticated-user-integration
git add .env.example
git add INTERNAL-JWT.md
git add src/main/resources/application.properties
git add src/test/java/com/japaneselearning/learning/controller/JwtAuthenticationTest.java
git add src/test/resources/application.properties
git diff --cached --stat
git commit -m "feat(learning): migrate JWKS consumers for authenticated service calls"
git push -u origin feat/authenticated-user-integration
```

### Root (after all submodule pushes)

```cmd
cd /d C:\Personal\springboot-project
git status --short
git switch -c feat/unified-jwks-internal-auth
git add .env.example
git add .env.jwks-api.example
git add .env.user-api.example
git add JWT-AUTHENTICATION.md
git add SECURITY-INTEGRATION-REPORT.md
git add docker-compose.yml
git add springboot-jwks-api
git add springboot-learning-api
git add springboot-user-api
git diff --cached --stat
git diff --cached --submodule=short
git commit -m "feat(compose): wire unified JWKS and isolated service authentication"
git push -u origin feat/unified-jwks-internal-auth
```

