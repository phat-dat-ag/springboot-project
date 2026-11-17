# Database migrations

| Application | Database | Migration directory | Compose runner | Path override |
| --- | --- | --- | --- | --- |
| hospital-user-api | MySQL | `db/migration/user` | `flyway-mysql` | `USER_API_MIGRATION_PATH` |
| hospital-api | PostgreSQL `hospital_db` | `springboot-hospital-api/src/main/resources/db/migration` | `flyway-postgres` and Spring Flyway | `HOSPITAL_API_MIGRATION_PATH` |

Compose mounts each directory read-only at `/flyway/sql` in its Flyway runner.
Each API starts after its runner finishes successfully. Hospital also loads the
same migrations from its packaged classpath for standalone operation.

Add versioned SQL files using `V<version>__<description>.sql`. Each database has
its own version history. Keep applied migration filenames and contents unchanged;
add a new migration for later schema changes.

The Hospital migration directory currently has no SQL migrations. `.gitkeep` preserves it
in fresh checkouts and is ignored by Flyway. Add PostgreSQL migrations there when
needed; MySQL migrations belong only in the user directory.

Copy `.env.example` to `.env` for new setups. The developer will manually recreate
this project's development databases. No data transfer or fake baseline migration
is supplied. Hibernate schema creation/update and Flyway clean are disabled for
Hospital API. Future entities require reviewed PostgreSQL migrations first.
