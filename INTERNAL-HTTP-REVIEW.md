# Phase 1/2 internal HTTP integration review

Review date: 2026-11-05. Scope: User's internal user lookup and Learning's HTTP caller only.

## A. Reviewed scope and contract

- Root: repository/submodule status and diffs, branch naming, `.gitmodules`, `.env.example`,
  `docker-compose.yml`, `db/README.md`, and `JWT-AUTHENTICATION.md`.
- User: internal and external user controllers, `UserManagementService` and implementation,
  repository lookup, `UserDTO`/`UserResponse`, response wrappers, exception advice/error codes,
  security and correlation filters, application configuration, Maven setup and test conventions.
- Learning: diagnostic controller/service, `UserServiceClient`, DTOs, client configuration,
  endpoint properties, existing caller interceptor, exception advice/error codes, response
  wrappers, correlation filter, security/OpenAPI configuration, Maven setup and tests.
- Also read User's JWT notes and both modules' generated HELP documentation. No applicable
  `AGENTS.md` files were found in the workspace or ancestor directories checked.

The current working-tree User controller returns `UserResponse` directly. This differs from
the older envelope discussed during debugging. Preserve the current, working contract:

| Route | Success | Authentication |
| --- | --- | --- |
| User `GET /internal/users/{id}` | `{"user":{...}}` | Temporarily unauthenticated, existing rule unchanged |
| Learning `GET /api/v1/learning/internal-test/users/{id}` | `{"user":{...}}` | Existing USER/ADMIN bearer authentication unchanged |
| User `GET /admin/users/{id}` | Existing `APIResponse` with `data.user` | Existing ADMIN requirement unchanged |

User's missing-user response remains 404 / `USER_NOT_FOUND`. Learning's upstream failures
remain 500 / `INTERNAL_SERVER_ERROR` with the existing response envelope. No new status-code
mapping, internal JWT, signing, token forwarding, retries or JWKS behavior was introduced.

## B. Strengths

- Separate User internal controller reuses existing read-only transactional business logic.
- Narrow DTOs contain no passwords, credentials or token fields; both services agree on fields.
- Constructor injection and a qualified HTTP client avoid ambiguous dependency selection.
- The cloned Spring-managed builder retains headers/interceptors and message converters.
- Existing caller metadata is reused without adding authentication or another interceptor.
- Endpoint and timeout settings already use the project's environment/property conventions.

## C. Findings

| Severity | Finding | Disposition |
| --- | --- | --- |
| Critical | No additional critical defect found within the agreed temporary unauthenticated phase | No security architecture changes |
| Important | Connect/read timeout properties were declared but never applied | Fixed for the User client only; validate finite millisecond limits |
| Important | Empty, null, incorrectly wrapped or wrong-user 200 responses could produce empty/incorrect results | Reject missing user/ID and ID mismatch; preserve valid response shape |
| Important | Default HTTP exceptions include upstream response bodies; generic exception logging could expose them | Convert client failures to existing safe business exception; log only status or exception type |
| Important | Learning test properties lacked the new User endpoint, breaking full application contexts | Supply isolated test settings |
| Important | Root `.env` User-client overrides were not forwarded by Compose | Forward/document the four existing settings |
| Important | Shared User exception advice returns 500 for malformed UUID parameters | Recorded and preserved; fixing shared advice changes existing external behavior |
| Important | Correlation IDs differ across services because User's shared filter generates a new ID | Outbound header is verified; shared filter left unchanged to preserve established behavior |
| Optional | Internal User controller inherited `BaseController` without using it | Removed unused inheritance |
| Optional | Thin Learning service has no interface; interceptor name mentions JWKS | Left alone: no demonstrated need for more abstraction or shared-code renaming |
| Optional | Existing JWT tests assume authority array order | Full-suite failure reported; unrelated authentication test left unchanged |

The temporary User endpoint remains reachable without credentials wherever the existing service
listener is reachable. That is the explicitly retained phase boundary, not a claim of production
service authentication.

## D. Changes made during this review

Paths below are relative to the named repository. Previously untracked Phase 1/2 implementation
files are included in delivery commands, even when their contents required no review edits.

| Repository | File | Reason |
| --- | --- | --- |
| User | `src/main/java/com/japaneselearning/user/controller/internal/InternalUserController.java` | Remove unused base-class inheritance; retain direct DTO return and business-service reuse |
| User | `src/test/java/com/japaneselearning/user/controller/internal/InternalUserControllerTest.java` | Six MVC/security regression tests for success, not-found, malformed ID, external admin rules/envelope, other internal paths |
| Learning | `src/main/java/com/japaneselearning/learning/client/UserServiceClient.java` | Validate successful payload and sanitize upstream failures using existing exceptions |
| Learning | `src/main/java/com/japaneselearning/learning/config/ServiceClientConfig.java` | Apply finite connect/read timeouts to User client only |
| Learning | `src/main/java/com/japaneselearning/learning/config/ServiceEndpointProperties.java` | Fail early for missing endpoint settings and invalid timeout bounds |
| Learning | `src/test/resources/application.properties` | Complete new client settings for Spring context tests |
| Learning | `src/test/java/com/japaneselearning/learning/client/UserServiceClientTest.java` | Nineteen real local-HTTP checks, including parsing, metadata, failures, read timeout, unavailability and configuration bounds |
| Learning | `src/test/java/com/japaneselearning/learning/controller/InternalUserControllerTest.java` | Three MVC checks for current security, success shape and generic upstream error envelope |
| Learning | `src/test/java/com/japaneselearning/learning/controller/OpenApiDocumentationTest.java` | Check diagnostic endpoint's existing Swagger bearer declaration |
| Learning | `src/test/java/com/japaneselearning/learning/client/JwksServiceClientTest.java` | Remove unrelated User setup; restored to committed contents, so no delivery change |
| Root | `docker-compose.yml`, `.env.example` | Pass through/document existing User-client environment settings, retaining defaults |
| Root | `INTERNAL-HTTP-REVIEW.md` | Record scope, decisions, validation and manual Git delivery |

Finite timeouts: defaults are 3s connect and 5s read; each configured value must convert to
1..2147483647 milliseconds. The read timeout bounds a blocking read, not the total request
duration. Requests are not retried automatically by application code.

## E. Intentionally unchanged

- User and Learning security rules, JWT configuration and all JWKS source/configuration.
  The pre-existing root JWKS submodule pointer change is unrelated and excluded from delivery.
- User business service/repository, external controllers, response envelopes, DTOs and shared
  exception/correlation filters; preserve existing business and external API behavior.
- Learning diagnostic endpoint, service forwarding layer, DTOs and shared exception advice;
  keep current routes/contracts without a stylistic refactor.
- Dependencies, Maven versions, migrations and secrets; no new framework or test dependency.
- Existing ordering-sensitive JWT test, which is outside this integration refinement.

## F. Validation

- User `mvnw.cmd -B -ntp test`: **39 passed**, including six new MVC/security tests.
- Learning full `mvnw.cmd -B -ntp test`: **50 run, 49 passed, 1 failed**. The failure is
  existing `JwtAuthenticationTest.adminTokenWithV2`: `$.data.authorities[0]` expected
  `ROLE_ADMIN`, received `FACTOR_BEARER`. It asserts ordering rather than membership;
  this review does not alter authentication production code or that test.
- Learning focused suite: **27 passed**. Command:
  `mvnw.cmd -B -ntp "-Dtest=UserServiceClientTest,InternalUserControllerTest,OpenApiDocumentationTest,JwksServiceClientTest,JwksCallerInterceptorTest" test`.
  It includes client, controller, OpenAPI and existing caller/interceptor tests.
- Maven test runs compiled production and test sources in both affected services.
- `docker compose config --quiet`: passed. Git diff whitespace checks: passed.
- HTTP client checks use the real configured RestClient over loopback TCP against a local
  JDK HTTP server, not a stubbed RestClient. Read-timeout behavior and connection refusal
  are exercised. A real remote connect timeout is not simulated; its configuration is applied
  and validated. MVC checks use real security chains with mocked business services/JWT decoder.
- User's MVC response fields match the Learning HTTP fixture (`user`, UUID, activation flag,
  local timestamps). No envelope was added. External User envelope/security and Learning
  route/security are covered by regression checks.
- No deployment/rebuild, database-backed two-service integration run, or end-to-end bearer
  authentication run was performed for these edits. No such success is claimed.
- Postman simulation/status unavailable: CLI exits because a managed Private Cloud registry
  manifest cannot be read. No Postman artifacts, account setup or deployment was added.
- Initial runs found the missing Learning test configuration (fixed) and User's existing
  malformed-ID 500 behavior (documented, not changed). No failing integration test is hidden.

## G. Remaining current-phase recommendations

- Keep the current response shape covered by these tests when updating either service.
- Plan a separate compatibility decision before changing Learning's 500 mapping to propagate
  User's 404 or introduce 502/504. Do not silently change this phase's established contract.
- Decide separately whether to accept validated inbound correlation IDs in shared filters and
  return 400 for malformed UUIDs across User APIs; both affect behavior beyond this controller.
- Smoke-test the rebuilt services with existing test data and an existing caller token before
  deploying. No database creation or credentials are needed for the committed regression suite.

## Manual Git delivery (Windows CMD)

No branch switching, staging, committing, pushing or destructive Git commands were executed.
Existing branches use `feat/`, `fix/` and `chore/`; the proposed branches use `feat/` because
the Phase 1/2 implementation is still uncommitted. Run each block only after the preceding
block succeeds. Inspect any already staged files first: the explicit adds below do not unstage
unrelated changes. Commands assume the currently inspected `develop` branches.

### 1. User submodule

```cmd
cd /d C:\Personal\springboot-project\springboot-user-api
git status --short
git diff --cached --name-only
git switch -c feat/internal-user-api
git add src/main/java/com/japaneselearning/user/config/SecurityConfig.java
git add src/main/java/com/japaneselearning/user/controller/internal/InternalUserController.java
git add src/test/java/com/japaneselearning/user/controller/internal/InternalUserControllerTest.java
git diff --cached --stat
git commit -m "feat(user): expose and test internal user lookup"
git push -u origin feat/internal-user-api
```

The security file contains the pre-existing Phase 1 permission for `/internal/users/*`.
This review did not edit that rule, but the initial implementation needs it in its commit.

### 2. Learning submodule

```cmd
cd /d C:\Personal\springboot-project\springboot-learning-api
git status --short
git diff --cached --name-only
git switch -c feat/user-service-http-integration
git add src/main/java/com/japaneselearning/learning/client/UserServiceClient.java
git add src/main/java/com/japaneselearning/learning/config/ServiceClientConfig.java
git add src/main/java/com/japaneselearning/learning/config/ServiceEndpointProperties.java
git add src/main/java/com/japaneselearning/learning/controller/InternalUserController.java
git add src/main/java/com/japaneselearning/learning/dto/InternalUserDTO.java
git add src/main/java/com/japaneselearning/learning/dto/response/InternalUserResponse.java
git add src/main/java/com/japaneselearning/learning/service/impl/InternalUserService.java
git add src/main/resources/application.properties
git add src/test/java/com/japaneselearning/learning/client/UserServiceClientTest.java
git add src/test/java/com/japaneselearning/learning/controller/InternalUserControllerTest.java
git add src/test/java/com/japaneselearning/learning/controller/OpenApiDocumentationTest.java
git add src/test/resources/application.properties
git diff --cached --stat
git commit -m "feat(learning): integrate bounded internal user HTTP client"
git push -u origin feat/user-service-http-integration
```

### 3. Root, only after both submodule commits and pushes succeed

```cmd
cd /d C:\Personal\springboot-project
git status --short
git diff --cached --name-only
git switch -c feat/learning-user-http-integration
git add .env.example
git add docker-compose.yml
git add INTERNAL-HTTP-REVIEW.md
git add springboot-user-api
git add springboot-learning-api
git diff --cached --stat
git diff --cached --submodule=short
git commit -m "feat(compose): wire learning-to-user HTTP integration"
git push -u origin feat/learning-user-http-integration
```

The root stages only the newly committed User/Learning pointers. Do not stage
`springboot-jwks-api`, run `git add .`, or commit test logs/real environment files.
When submodule PRs are squash-merged or rebased, update the root pointers to the final reachable
commits before merging the root PR.
