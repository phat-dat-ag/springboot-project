# Database migrations

| Application | Database | Migration directory | Compose runner | Path override |
| --- | --- | --- | --- | --- |
| hospital-user-api | MySQL | `db/migration/user` | `flyway-mysql` | `USER_API_MIGRATION_PATH` |
| hospital-api | PostgreSQL `clinical_db` | `db/migration/hospital` | `flyway-postgres` and Spring Flyway | `HOSPITAL_API_MIGRATION_PATH` |

Compose mounts each directory read-only at `/flyway/sql` in its Flyway runner.
Each API starts after its runner finishes successfully. Hospital also loads the
same migrations from its packaged classpath for standalone operation.

Add versioned SQL files using `V<version>__<description>.sql`. Each database has
its own version history. Keep applied migration filenames and contents unchanged;
add a new migration for later schema changes.

The Hospital directory contains V1–V11 for 29 tables, including the P02 replay key table. It is the
single SQL source; Maven packages these files as `classpath:db/migration`.
See [the full database reference](../springboot-hospital-api/docs/DATABASE.md).

Both `.env` (local, ignored) and `.env.example` select `POSTGRES_DB=clinical_db`
and `HOSPITAL_API_MIGRATION_PATH=./db/migration/hospital`. Credentials remain
external. `clinical-database-init` creates the selected database only if missing,
including on an existing PostgreSQL volume, before `flyway-postgres` runs.
It uses the configured PostgreSQL role; that role needs CREATEDB. Existing
databases are preserved. Existing volumes must have matching user/passwords;
changing environment credentials does not change an existing database role.

Run from the repository root:

```powershell
docker compose config --quiet
docker compose up -d --build hospital-api
```

This brings up the API's existing dependencies; it does not reset volumes.
The Flyway runner applies the migrations before API startup. Inspect with
`docker compose logs clinical-database-init flyway-postgres`. Do not point at
an unrelated or nonempty legacy schema. Flyway baseline and clean are disabled;
previously applied migrations must never be edited. No User or JWKS SQL is added.
