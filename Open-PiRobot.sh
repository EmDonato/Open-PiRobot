#!/usr/bin/env bash

set -u

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Open-PiRobot requires Python 3.10 or newer." >&2
    exit 2
fi

if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "Open-PiRobot requires Python 3.10 or newer." >&2
    exit 2
fi

if ! python3 -c 'import yaml' >/dev/null 2>&1; then
    echo "Open-PiRobot requires PyYAML. Install it with: sudo apt install python3-yaml" >&2
    exit 2
fi

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m scripts.robot_manager --project-root "$PROJECT_ROOT" "$@"
