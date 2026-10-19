#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Keep service state and credentials out of version control.
state="$PWD/.local-setup"
mkdir -p "$state"
chmod 700 "$state"
if ! command -v uv >/dev/null 2>&1 && [[ -x "$state/tools/bin/uv" ]]; then
  export PATH="$state/tools/bin:$PATH"
fi
if ! command -v uv >/dev/null 2>&1; then
  python3.12 -m venv "$state/tools"
  "$state/tools/bin/pip" install uv
  export PATH="$state/tools/bin:$PATH"
fi
export UV_CACHE_DIR="$state/uv-cache"
uv sync --locked --python python3.12

# Homebrew's PostgreSQL executables may not be on PATH.
if ! command -v initdb >/dev/null 2>&1 && command -v brew >/dev/null 2>&1; then
  for formula in postgresql@18 postgresql@17 postgresql@16 postgresql@15 postgresql@14 postgresql; do
    prefix="$(brew --prefix "$formula" 2>/dev/null || true)"
    if [[ -n "$prefix" && -x "$prefix/bin/initdb" ]]; then
      export PATH="$prefix/bin:$PATH"
      break
    fi
  done
fi
for executable in initdb pg_ctl psql createdb redis-server redis-cli; do
  command -v "$executable" >/dev/null || { echo "Missing prerequisite: $executable" >&2; exit 1; }
done

# Read only the needed settings, without evaluating .env as shell code.
settings_exports="$(uv run python - <<'PY'
import shlex
from app.config import db_settings as s
for name, value in {'PGPORT': s.POSTGRES_PORT, 'PGUSER': s.POSTGRES_USERNAME,
                    'PGPASSWORD': s.POSTGRES_PASSWORD, 'PGDATABASE': s.POSTGRES_DB,
                    'REDIS_PORT': s.REDIST_PORT}.items():
    print(f'export {name}={shlex.quote(str(value))}')
if s.POSTGRES_SERVER not in ('localhost', '127.0.0.1') or s.REDIS_HOST not in ('localhost', '127.0.0.1'):
    raise SystemExit('This setup script requires local database and Redis hosts.')
PY
)"
eval "$settings_exports"
export PGHOST=127.0.0.1
if [[ ! -f "$state/postgres/PG_VERSION" ]]; then
  printf '%s\n' "$PGPASSWORD" > "$state/pg-password"
  chmod 600 "$state/pg-password"
  initdb -D "$state/postgres" -U "$PGUSER" --pwfile="$state/pg-password" --auth-host=scram-sha-256 --auth-local=trust
  rm "$state/pg-password"
fi
if ! pg_ctl -D "$state/postgres" status >/dev/null 2>&1; then
  pg_ctl -D "$state/postgres" -l "$state/postgres.log" -o "-h 127.0.0.1 -p $PGPORT -k $state" start
fi
if [[ "$(psql -d postgres -tA -v "db_name=$PGDATABASE" <<'SQL'
SELECT 1 FROM pg_database WHERE datname = :'db_name';
SQL
)" != 1 ]]; then
  createdb "$PGDATABASE"
fi
if ! redis-cli -h 127.0.0.1 -p "$REDIS_PORT" ping >/dev/null 2>&1; then
  redis-server --bind 127.0.0.1 --port "$REDIS_PORT" --daemonize yes --dir "$state" --pidfile "$state/redis.pid" --logfile "$state/redis.log"
fi
uv run alembic upgrade head
uv run alembic current

# A dedicated API process is left running for assignment work.
if [[ -f "$state/api.pid" ]] && kill -0 "$(cat "$state/api.pid")" 2>/dev/null; then
  echo 'Reusing the API process started by this script.'
else
  nohup uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$state/api.log" 2>&1 &
  echo "$!" > "$state/api.pid"
fi
uv run python -m scripts.verify_local_setup
echo 'Ready: http://127.0.0.1:8000/docs (also /scalar).'
echo "Service logs and local login credentials: $state"
