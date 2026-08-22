#!/bin/bash
set -e

docker compose -f modules/teleoperation/compose.yaml up --watch
