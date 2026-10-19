# Communicator backend

FastAPI, PostgreSQL, and Redis application for the backend take-home assignment. See [REPOSITORY_GUIDE.md](REPOSITORY_GUIDE.md) and the [API](architecture_readme/README_API.md) and [webhook](architecture_readme/README_WEBHOOK.md) architecture guides for the existing design.

## Run with Docker Compose

Install Docker with Compose, then create `.env` from `.env.example` and replace the placeholder values for `POSTGRES_PASSWORD` and `JWT_SECRET`. Set a private `WEBHOOK_SECRET` too. Keep `.env` out of version control.

```bash
cp .env.example .env
docker compose up --build -d
```

Compose starts PostgreSQL and Redis, waits for both to become healthy, applies all Alembic migrations, then starts the API. Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) or `/scalar`. `GET /` is the health endpoint. Database data remains in the `postgres_data` volume across restarts. Use `docker compose logs -f api` to inspect startup errors and `docker compose down` to stop services.

The API starts with an empty application database. To exercise a status webhook, register via `POST /user/signup`, log in via `POST /user/token` (email goes in the form's `username` field), create a campaign named `Weekly Teacher Check-in` via authenticated `POST /campaign/`, then run:

```bash
docker compose exec api python -m scripts.seed
```

The seed reuses existing sample records. It provides a cohort, teachers, and an outbound message with `provider=fake_provider` and `provider_message_id=msg_out_001`. Send status callbacks to `POST /webhook/status` with `X-Webhook-Secret` set to `WEBHOOK_SECRET`. For example:

```json
{"provider":"fake_provider","provider_event_id":"example_delivery_001","provider_message_id":"msg_out_001","status":"delivered","event_timestamp":"2026-09-29T19:02:00"}
```

`POST /webhook/message` accepts incoming messages from known teacher phones. See the webhook architecture guide for its payload.

## Create a teacher

`POST /teacher/` requires a bearer token from `/user/token` and a pre-existing cohort. Example body:

```json
{"name":"Aisha","phone":"919876543210","cohort_id":"<cohort UUID>"}
```

It returns `201` with the new teacher. A missing cohort returns `404`; a phone already assigned to another teacher returns `409`. The phone must be 8–15 digits, with no punctuation. Cohorts currently come from the seed; there is no cohort creation API.

## Local development and tests

The existing local helper remains available on macOS/Linux with Python 3.12, PostgreSQL, and Redis installed:

```bash
bash scripts/setup_local.sh
```

It installs dependencies with `uv`, starts local PostgreSQL and Redis, applies migrations, creates the example campaign through the API, runs the seed, and checks both webhook flows. Local service state and generated login credentials are stored under `.local-setup/`. The script uses the connection settings in `.env` and requires local database and Redis hosts.

With the local services running, run the complete test suite with one command:

```bash
.venv/bin/python -m pytest -q
```

Tests create a uniquely named PostgreSQL database for each test, run all migrations, create their own fixtures, and drop the database afterward. They never read seed data. The PostgreSQL user in `.env` must be able to create databases. Tests do not require Redis; they replace the blacklist lookup only in the teacher authentication test.

If setting up manually, run `uv sync --locked`, start PostgreSQL and Redis using `.env`, create `POSTGRES_DB`, run `uv run alembic upgrade head`, and start `uv run uvicorn app.main:app --reload`.
