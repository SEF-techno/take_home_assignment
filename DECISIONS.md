# Decisions

## Task 1: Run the application

I ran the provided local setup helper. Its first attempt stopped at Alembic because SQLAlchemy's async engine needs `greenlet`, which the project did not declare. I added `greenlet` to the runtime dependencies and regenerated the lockfile. The second attempt applied every migration, started the API, created the campaign through authentication, ran the seed twice, exercised both webhooks and duplicate delivery, and checked logout against Redis. The local helper also needs PostgreSQL and Redis executables installed; it handles a Homebrew PostgreSQL path but is aimed at macOS/Linux.

## Task 2: Automated tests

I used pytest with one temporary PostgreSQL database per test. Every database receives the real Alembic migrations. The fixture creates the cohort, teacher, campaign, and outbound message it needs, so the tests do not rely on the development seed. FastAPI's session dependency is overridden to point at that database; connection pooling is disabled so the synchronous test client and fixture event loops can safely share the engine. Each database is dropped in teardown. The documented command is `.venv/bin/python -m pytest -q`.

The three requested tests cover missing, wrong, and correct webhook secrets; duplicate event persistence; and chronological status after reversed delivery. I added a teacher API integration test because authorization, persistence, duplicate handling, and audit behavior are central to the new endpoint. Only that test replaces the Redis blacklist lookup; it still uses a signed JWT and the real user lookup.

The out-of-order test exposed a correctness issue: new messages initialize `status_updated_at` to creation time. If the first provider event has an earlier timestamp, the old code retained creation time, even though no provider status existed then. The service now uses the first event's timestamp, then moves forward only for newer events. This changes service behavior without changing the schema.

## Task 3: Teacher creation

I added `POST /teacher/` with a request schema, a response schema, a service, a dependency, and a router. It uses the existing authenticated user dependency. The service verifies that the cohort exists, rejects a duplicate phone, and writes the teacher and an audit event in one transaction. I added a unique database constraint on `teacher.phone` because the inbound webhook expects one teacher for a phone; without it, duplicate records can make its `scalar_one_or_none()` lookup fail. The migration is additive and applies to an unmodified baseline; a database with pre-existing duplicate teacher phones must be cleaned before applying it.

Names are trimmed and cannot be blank. Phones are 8–15 digits to fit the provider-neutral numeric format already used by the seed. I did not add a country-code policy because the scaffold has no provider-specific phone rules. I did not add cohort creation or teacher list/update/delete endpoints because the task only asks for creation. Cohorts can currently be supplied by the seed.

## Task 4: Containerization

`docker compose up --build -d` builds the API image and starts PostgreSQL and Redis. Service health checks gate API startup, and the API applies Alembic migrations before serving. The database uses a named volume. The `.env` file supplies secrets and database names; Compose overrides hostnames with service names. Seed data remains an explicit demonstration step because the application requires a campaign to be created through its authenticated API before seeding. I verified the Compose build and startup, every migration on an empty container database, health and OpenAPI responses, signup/login and campaign creation, the in-container seed, and duplicate, out-of-order, and inbound webhook calls.

## Overall

I kept the changes close to the existing router, schema, service, and SQLModel patterns and tested behavior through HTTP and the database. I deliberately left the provider simulation, cohort API, and broader authorization model alone because they are outside this assignment's scope.

Two existing concerns are worth raising. First, webhook idempotency checks for an existing event before insert, while the database unique constraint is the final defense. Two concurrent deliveries can still race: one may receive an `IntegrityError` instead of a successful duplicate response. A robust fix would catch the unique violation in a savepoint or insert with `ON CONFLICT`, then read the existing event. Second, campaign mutations commit the entity and audit event separately; an audit failure can leave a committed mutation without its record. I made teacher creation atomic but did not refactor unrelated campaign behavior.

With more time, I would add concurrent webhook delivery tests and fix that race, make audit writes atomic across all services, and add Compose startup verification to CI. The database-backed tests also require a local PostgreSQL role that can create and drop databases; a dedicated test container could make that prerequisite easier to supply.
