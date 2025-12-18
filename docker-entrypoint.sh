#!/usr/bin/env bash
set -euo pipefail

SERVICE=${SERVICE:-backend}
BACKEND_PORT=${BACKEND_PORT:-8000}
CHAINLIT_PORT=${CHAINLIT_PORT:-8001}

case "$SERVICE" in
  backend)
    exec uvicorn backend.app.main:app --host 0.0.0.0 --port "$BACKEND_PORT"
    ;;
  chainlit)
    exec chainlit run frontend/chainlit_app.py -h 0.0.0.0 -p "$CHAINLIT_PORT"
    ;;
  all)
    uvicorn backend.app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
    backend_pid=$!

    chainlit run frontend/chainlit_app.py -h 0.0.0.0 -p "$CHAINLIT_PORT" &
    chainlit_pid=$!

    trap "kill -TERM $backend_pid $chainlit_pid" TERM INT
    wait -n
    exit $?
    ;;
  *)
    exec "$@"
    ;;
esac
