# Hospital Management System

Project identifier: `hospital-management`. Compose project: `hospital_dev`.

| Module | Responsibility | Maven coordinates |
| --- | --- | --- |
| `springboot-user-api` | Existing authentication and user management on MySQL | `com.hospitalmanagement:hospital-user-api` |
| `springboot-hospital-api` | PostgreSQL technical foundation; no clinical features yet | `com.hospitalmanagement:hospital-api` |
| `springboot-jwks-api` | Protected shared public-key publisher | Unchanged |

The root Maven reactor builds User and Hospital. JWKS is excluded so Maven cannot
write inside its protected tree. Compose builds its unchanged Dockerfile.

Copy `.env.example`, `.env.user-api.example`, `.env.hospital-api.example`, and
`.env.jwks-api.example` to their names without `.example`. Supply credentials and
existing key paths. Keep issuers, key IDs and ownership aligned. Never commit
filled env files or private keys.

The developer will manually remove this project's obsolete Docker resources
before rebuilding. This migration does not operate containers or volumes.
User remains on MySQL `hospital_user_db`; Hospital uses PostgreSQL `hospital_db`.
Services use `hospital-network`. Existing configured host ports are preserved.

Run `mvn validate`, `mvn test`, and `python validate_rebranding.py` for checks.
The Python command renders Compose without operating containers. See the
[Hospital API guide](springboot-hospital-api/README.md),
[debugging guide](DEBUGGING.md), and [observability guide](observability/README.md).

Shared security contracts retain legacy identity strings and key paths. The
Hospital submodule keeps its existing remote URL because remote changes are
outside this task. `HOSPITAL-MIGRATION-REPORT.md` records protected exceptions,
validation limits and manual Git/submodule steps.
