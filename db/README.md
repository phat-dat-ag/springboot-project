# Database migrations

| Application | Database | Migration directory | Compose runner | Path override |
| --- | --- | --- | --- | --- |
| user-api | MySQL | `db/migration/user` | `flyway-mysql` | `USER_API_MIGRATION_PATH` |
| learning-api | PostgreSQL | `db/migration/learning` | `flyway-postgres` | `LEARNING_API_MIGRATION_PATH` |

Compose mounts each directory read-only at `/flyway/sql` in its Flyway runner.
Each API starts after its runner finishes successfully. The APIs do not load
these host directories themselves.

Add versioned SQL files using `V<version>__<description>.sql`. Each database has
its own version history. Keep applied migration filenames and contents unchanged;
add a new migration for later schema changes.

The learning directory currently has no SQL migrations. `.gitkeep` preserves it
in fresh checkouts and is ignored by Flyway. Add PostgreSQL migrations there when
needed; MySQL migrations belong only in the user directory.

Copy `.env.example` to `.env` for new setups. Existing setups must update the two
path overrides to the directories above (relative to the Compose project, or
absolute). Rebuild/recreate through `docker compose up -d --build`; moving the
files does not require deleting database volumes or changing migration history.
