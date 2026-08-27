#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "===== Startup begin ====="

echo "Setup teleoperation container [1/3]"

bash "$SCRIPT_DIR/joy_start.sh"

echo "Setup teleoperation container [2/3]"

bash "$SCRIPT_DIR/sensor_fusion_start.sh"

echo "Setup main container [3/3]"

docker compose -f "$PROJECT_DIR/compose.yaml" up -d --build

echo "===== Startup end ====="

