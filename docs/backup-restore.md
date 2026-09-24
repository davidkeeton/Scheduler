# Alpha PostgreSQL backup and restore

Run these commands from the directory containing `compose.yaml`. Store the dump off the Docker host and protect it as personnel data. Choose a private path and keep more than one dated copy.

## Backup

```sh
docker compose exec -T db sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > scheduler-backup.dump
```

Check that the file is nonempty and retain a copy away from the server. A Docker volume alone is not a backup.

## Restore test on a separate alpha stack

Stop writes to that test stack. Restore into an empty test database using its own Compose project/volume; never test restore against the live database. For example, after starting a fresh stack in a separate directory:

```sh
docker compose stop api web
docker compose exec -T db sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < scheduler-backup.dump
docker compose start api web
```

Verify teams, people, a past published week, and a saved publication revision in the restored app. Record the backup date and restore result. Restoring replaces the target database's records; use a test stack first.
