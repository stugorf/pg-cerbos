# Repository Guidelines

## Project Structure & Module Organization

This repository is a Docker Compose stack for Cerbos-authorized data access across Postgres, Trino/Iceberg, MinIO/Nessie, PuppyGraph, and a policy registry UI.

- `compose.yml` defines all local services and ports.
- `policy-registry/backend/` contains the FastAPI service, auth, query, Cerbos, Trino, PuppyGraph, NL-to-Cypher, and chart code.
- `policy-registry/frontend/static/` contains the static HTML/CSS/JS UI served by Nginx.
- `postgres/init/` contains database schema and seed SQL loaded by Postgres containers.
- `cerbos/` stores Cerbos config and YAML policies.
- `puppygraph/` stores graph schema config.
- `tests/` and `scripts/` contain shell-based verification and setup flows.
- `docs/` contains feature notes, quickstarts, and architecture references.

## Build, Test, and Development Commands

- `just up` starts the Compose stack.
- `just up-build` starts the stack and rebuilds images.
- `just down` stops services and removes volumes.
- `just ps` shows container status.
- `just logs` tails service logs.
- `just init` runs post-start setup.
- `just rebuild-backend` rebuilds and restarts the backend.
- `just rebuild SERVICE` rebuilds a named service.
- `just test`, `just test-nl-cypher`, `just test-cypher-parser`, and `just test-puppygraph-all` run focused test suites.

## Coding Style & Naming Conventions

Python code uses module-level FastAPI patterns. Keep functions snake_case, classes PascalCase, and constants UPPER_SNAKE_CASE. Prefer explicit request/response models in `*_models.py`. Static frontend code currently lives mostly in `auth.html`; keep DOM ids descriptive and aligned with tab names, for example `graph-query-input`.

SQL init scripts should be idempotent using `IF NOT EXISTS`, `ON CONFLICT`, or guarded `\gexec` database creation.

## Testing Guidelines

Backend unit tests are Python files named `test_*.py` under `policy-registry/backend/`. PuppyGraph and integration checks are shell scripts under `tests/` and `scripts/`. Run the smallest relevant test first, then broader checks for shared auth, policy, or query behavior. For UI changes, rebuild the frontend container and verify `http://localhost:8083/auth.html`.

## Commit & Pull Request Guidelines

Recent commit messages use short prefixes such as `enh:`, `fix:`, and `doc:`. Keep messages imperative and scoped, for example `fix: seed auth users into policy_store`.

Pull requests should include a summary, affected services, verification commands, and screenshots for visible UI changes. Call out schema, seed data, port, or Compose changes because they often require volume recreation.

## Security & Configuration Tips

Do not commit real credentials. Use `.env` overrides for `OPENAI_API_KEY`, `SECRET_KEY`, and `PUPPYGRAPH_PASSWORD`. Existing Docker volumes do not replay `postgres/init/`; use `just down` only when resetting local data is acceptable.
