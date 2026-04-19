#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

ACTION="${1:-up}"
shift || true

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but was not found in PATH." >&2
  exit 1
fi

if [[ ! -f ".env" ]]; then
  echo "Missing .env. Copy .env.example first:" >&2
  echo "  cp .env.example .env" >&2
  exit 1
fi

case "${ACTION}" in
  up)
    docker compose up --build "$@"
    ;;
  down)
    docker compose down "$@"
    ;;
  build)
    docker compose build "$@"
    ;;
  logs)
    docker compose logs -f "$@"
    ;;
  *)
    echo "Usage: $0 {up|down|build|logs} [docker compose args...]" >&2
    exit 1
    ;;
esac
