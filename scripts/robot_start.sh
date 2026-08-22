#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "===== Startup begin ====="

echo "Setup teleoperation container [1/2]"

bash "$SCRIPT_DIR/joy_start.sh"

echo "Setup main container [2/2]"

docker compose -f "$PROJECT_DIR/compose.yaml" up -d

echo "===== Startup end ====="

docker compose -f "$PROJECT_DIR/compose.yaml" exec open_pi_main bash