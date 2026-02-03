#!/usr/bin/env sh
set -e

python -m app.db.bootstrap
exec python -m app.main
