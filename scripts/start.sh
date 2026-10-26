#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
case "${1:-synthetic}" in
  synthetic)
    docker compose -f compose.synthetic.yaml up --build --wait --wait-timeout 180
    docker compose -f compose.synthetic.yaml exec -T api python -m demo.verify --base-url http://web:8080
    ;;
  live)
    if [ ! -f .env ]; then
      cp .env.example .env
      echo 'Created .env. Fill ALPHA_LLM_API_KEY and ALPHA_LLM_MODEL, then run again.' >&2
      exit 1
    fi
    mkdir -p inputs/csv parser/inputs/analytics
    docker compose --profile search up --build --wait --wait-timeout 180
    ;;
  *) echo 'Usage: sh scripts/start.sh [synthetic|live]' >&2; exit 2 ;;
esac
