# Progress Log

## 2026-06-24 — Local Postgres access for external tooling (VS Code DB client)

**Status: ✅ Done & verified from host.**

Goal: connect to the Dockerized Postgres directly from a VS Code database client
(SQLTools / PostgreSQL extension), separate from the app.

What changed:
- **Host port remapped to `5433`.** Host port `5432` is already occupied by a native
  PostgreSQL install on this machine (PID confirmed as `postgres`). To avoid connecting
  to the wrong server, `docker-compose.yml` now exposes the container as `5433:5432`.
  Inside the compose network the backend is unchanged (`db:5432`) — the app was not touched.
- Credentials reused from `.env` (not invented); OpenRouter key untouched.
- `db` container recreated; data preserved in the `pgdata` volume.

Verified from the host terminal (native `psql`/`pg_isready`, not from inside the container):
- `pg_isready -h localhost -p 5433` → *accepting connections*.
- Query returned 5 countries / 15 universities / 74 cost_items (our seeded data).
- `server_version` = 16.14 (Docker pgvector:pg16) — confirms the Docker DB, not the
  native PostgreSQL 18 on 5432.

### Connection details for the VS Code DB client
| Field | Value |
|-------|-------|
| Host | `localhost` |
| Port | `5433` |
| Database | `studyplanner` |
| Username | `studyplanner` |
| Password | `studyplanner` |
| SSL | disabled |

> Note: the app/backend keeps using the internal `db:5432` over the compose network;
> only the host-facing port changed. `.env` `DATABASE_URL` is intentionally left as
> `@db:5432` (internal) and must not be pointed at `localhost:5433`.
