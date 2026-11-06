# JWT authentication and unified JWKS

## Trust and routes

JWKS exposes one public GET mapping, `/api/v1/jwks/{owner}`. Supported lowercase owners are
`user` and `learning`; unknown or missing owners return 404 without any keys. Each response is
standard unwrapped `{"keys":[...]}`, with five-minute public caching and no private or owner fields.
Retired `/.well-known/jwks.json` and `/.well-known/learning/jwks.json` have no compatibility routes.

| Consumer | Trusted key source inside Docker | Claims/policy |
| --- | --- | --- |
| User external decoder | `http://jwks-api:8080/api/v1/jwks/user` | Existing User issuer and User/Admin roles |
| Learning inbound decoder | `http://jwks-api:8080/api/v1/jwks/user` | Existing User issuer, time/required-claim checks and User/Admin roles |
| User internal decoder | `http://jwks-api:8080/api/v1/jwks/learning` | Learning issuer/subject, User audience, RS256, internal+jwt, required kid/jti/iat/exp |
| Learning diagnostic client | `http://jwks-api:8080/api/v1/jwks/user` | Public-key retrieval only |

Trusted URLs are explicit configuration, never selected from unverified token claims. Internal
and external key sets remain separate even if a malicious token copies another issuer's claims.
Ownership is a required operator-configured enum, not inferred from key-ID prefixes.

User has ordered, stateless security chains. `/internal/**` uses only the internal decoder;
GET `/internal/users/*` requires `SERVICE_LEARNING`, and other internal requests are denied.
Missing or invalid tokens, including user JWTs, return 401. A valid service identity denied by
route policy receives 403. External endpoints retain their existing User/Admin authorization;
Learning tokens cannot authenticate there. No internal token is mapped to User/Admin roles.

Learning generates a fresh RS256 Internal JWT on each User-client request: `typ=internal+jwt`,
active Learning `kid`, `iss=sub=learning-service`, `aud=user-service`, current `iat`, `exp=iat+60s`
and random `jti`. The incoming user JWT is never forwarded. Unrelated clients receive no token.
Signature, issuer, subject, audience, type and time checks are separate from authorization.
A random jti does not itself provide replay protection. Production deployments should protect
bearer-token transport with TLS and restrict service network access.

## Environment ownership

The root `.env` supplies Compose interpolation, not arbitrary container variables. Compose maps
selected values explicitly. `.env.user-api`, `.env.learning-api` and `.env.jwks-api` are loaded
only into their respective service. Copy their `.example` files for a new checkout. Real files
are Git-ignored; preserve credentials and do not paste PEM contents or JWTs into any environment.

| Root variable | Consumer / purpose | Development value |
| --- | --- | --- |
| `JWT_ISSUER` | Existing User token issuer shared by both external decoders | Preserve existing deployment value |
| `USER_JWT_JWK_SET_URI` | User external key source | `http://jwks-api:8080/api/v1/jwks/user` |
| `LEARNING_JWT_JWK_SET_URI` | Learning inbound key source | `http://jwks-api:8080/api/v1/jwks/user` |
| `INTERNAL_JWT_JWK_SET_URI` | User internal key source | `http://jwks-api:8080/api/v1/jwks/learning` |
| `INTERNAL_JWT_ISSUER` | Trusted internal issuer | `learning-service` |
| `INTERNAL_JWT_SUBJECT` | Required service identity | `learning-service` |
| `INTERNAL_JWT_AUDIENCE` | Required recipient | `user-service` |
| `INTERNAL_JWT_CLOCK_SKEW` | Internal time tolerance, 0..30s | `5s` |
| `INTERNAL_JWT_MAX_LIFETIME` | Maximum issued lifetime, 1..300s | `300s` |
| `LEARNING_INTERNAL_JWT_ENABLED` | Enable Learning signer | `true` |
| `LEARNING_INTERNAL_JWT_ISSUER` | Learning issuer and subject | `learning-service` |
| `LEARNING_INTERNAL_JWT_AUDIENCE` | Learning token recipient | `user-service` |
| `LEARNING_INTERNAL_JWT_TTL` | Issued lifetime, whole seconds, 1..300s | `60s` |
| `USER_SERVICE_INTERNAL_JWT_ENABLED` | Attach generated token to User requests | `true` |
| `USER_SERVICE_BASE_URL` | Intended User destination | `http://user-api:8080` |
| `USER_SERVICE_GET_USER` | Internal lookup path | `/internal/users` |
| `USER_SERVICE_CONNECT_TIMEOUT` / `USER_SERVICE_READ_TIMEOUT` | Existing finite HTTP timeouts | `3s` / `5s` |
| `JWKS_SERVICE_BASE_URL` / `JWKS_SERVICE_GET_PUBLIC_KEYS` | Learning diagnostic client | `http://jwks-api:8080` / `/api/v1/jwks/user` |
| `USER_SIGNING_KEYS_DIR` / `JWKS_KEYS_DIR` | Host source directory for existing User files | `./key` |
| `LEARNING_SIGNING_KEYS_DIR` | Host source directory for Learning files | `./data/keys/learning` |

Type `internal+jwt` and algorithm RS256 are fixed security-profile constants, not permissive
runtime settings. User's internal properties bind under `app.security.internal-jwt`; Learning's
outbound signing properties use the same prefix independently in its own process.

Indexed private-key variables in each signer's env file are
`APP_SECURITY_SIGNING_KEYS_<n>_KID`, `..._PRIVATEKEYPATH`, and `..._ACTIVE`.
Each signer requires exactly one active key. User's first-key legacy PRIVATE_KEY_PATH spelling
is accepted as a fallback only; use canonical PRIVATEKEYPATH for all indices.
JWKS variables are `APP_SECURITY_JWKS_KEYS_<n>_KID`, `..._PUBLICKEYPATH`, and `..._OWNER`.
Use consecutive indices and unique IDs across owners. JWKS has no active-key-count restriction.
All configured public keys for an owner are published, including retained rotation keys.

## Key files and mounts

No files need moving, copying or regeneration:

```text
key/
  userservice-private-v1.pem
  userservice-private-v2.pem
  userservice-public-v1.pem
  userservice-public-v2.pem
data/keys/learning/
  learningservice-private-v1.pem
  learningservice-public-v1.pem
```

Compose uses read-only, individual-file bind mounts with host-path creation disabled:

| Container | Mounted key files |
| --- | --- |
| User | Its two private PEMs at `/run/keys/jwt/` |
| Learning | Its private PEM at `/run/keys/learning/` |
| JWKS | User's two public PEMs at `/run/keys/jwt/` and Learning's public PEM at `/run/keys/learning/` |

No private key is mounted into JWKS. Windows paths identify host files; `/run/keys/...` paths
are inside Linux containers. Files must be readable by runtime UID 10001. Adding rotation keys
requires another explicit file mount and indexed entry. Publish the new public key before
selecting its private key, retain old public keys until tokens and caches expire, then retire.
`kid` values must match the corresponding signer's header and must not be reused for new material.

## Build and deployment

Run `mvnw.cmd -B -ntp verify` in each submodule. Tests use generated keys and local HTTP servers.
Internal authentication tests use real decoders and both filter chains, including cross-issuer
spoofing and malformed/expired tokens. HTTP-client tests verify signature and per-request token
attachment without forwarding caller credentials. No production token or private key is logged.

From the root (Windows CMD):

```cmd
docker compose config --quiet
docker compose -p springboot_project up -d --build --no-deps jwks-api user-api learning-api
curl.exe http://localhost:8783/api/v1/jwks/user
curl.exe http://localhost:8783/api/v1/jwks/learning
curl.exe -i http://localhost:8781/internal/users/f05bf709-5cb8-4a4c-9ac4-e537b5579aef
```

Host ports are examples from the current deployment; inspect your root overrides. Container
traffic always uses Docker service names and port 8080. Do not run `down -v` or recreate databases.
For a local IDE process, explicitly supply host-accessible JWKS URLs and Windows private-file
paths; Compose env files are not automatically loaded by Java. Enable both Learning signing and
outbound attachment for a local authenticated integration run.

See `SECURITY-INTEGRATION-REPORT.md` for checks actually performed and manual Git delivery.
