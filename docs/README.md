# Open-PiRobot Container Manager

`Open-PiRobot.sh` is the stable entry point for the central container manager.
The shell file locates the project, checks Python, and uses `exec` to run the
modular implementation under `scripts/robot_manager/`. Components, aliases,
checks, and variants are declared in the ordered `config/robot.yaml` registry.

## Host prerequisites

The manager requires Python 3.10 or newer, PyYAML, Docker Engine, and Docker
Compose v2. On Ubuntu, install the host-side Python dependencies with:

```bash
sudo apt install python3 python3-yaml
```

The manager never installs dependencies, clones repositories, or updates Git
submodules automatically. ROS 2 remains inside the component containers.

## Syntax and default behavior

```bash
./Open-PiRobot.sh [--config PATH] [COMMAND] [TARGET ...] [VARIANT]
```

Running without arguments performs the default idempotent startup. For an
existing container it applies the current Compose configuration without a
build; for a missing container it builds, creates, and starts it.

The enabled default group is processed in registry order:

```text
stm32 -> lidar -> realsense -> fusion -> slam -> voice -> robot
```

`all` selects exactly that same group. `teleoperation` is enabled but excluded
from the default group and must be named explicitly. Explicit target selection
keeps the user-provided order and removes duplicates after alias resolution.

## Commands

| Command | Aliases | Behavior |
| --- | --- | --- |
| `build` | `--build` | Build images without hardware checks or container creation |
| `create` | `-c`, `--create` | Check hardware, build, create, and start containers |
| `start` | `-s`, `--start` | Check hardware and start containers that already exist |
| `stop` | `-t`, `--stop` | Stop existing containers |
| `restart` | `-r`, `--restart` | Check hardware and recreate existing containers without building |
| `remove` | `-x`, `--remove` | Stop and remove containers while preserving images and bind-mounted data |
| `status` | `--status` | Show each selected container state |
| `check` | `--check` | Validate Docker, Compose, and declared hardware checks |
| `logs` | `--logs` | Follow the last 50 lines and new output until interrupted |
| `list` | — | Show component aliases, enablement, and default-group membership |
| `validate-config` | — | Validate the registry and enabled Compose paths without Docker or hardware |
| `help` | `-h`, `--help` | Print the command reference |

Examples:

```bash
./Open-PiRobot.sh
./Open-PiRobot.sh build
./Open-PiRobot.sh create stm32 robot
./Open-PiRobot.sh restart stm32 robot
./Open-PiRobot.sh build teleoperation
./Open-PiRobot.sh logs stm32 fusion slam
./Open-PiRobot.sh list
./Open-PiRobot.sh validate-config
```

## Registered components

| Target | Aliases | Service | Container | Default |
| --- | --- | --- | --- | --- |
| `stm32` | `stm32_driver`, `open-pi-stm32-driver` | `stm32_driver` | `open-pi-stm32-driver` | yes |
| `lidar` | `lidar_driver`, `open-pi-lidar-driver` | `lidar_driver` | `open-pi-lidar-driver` | yes |
| `realsense` | `camera`, `realsense_driver`, `open-pi-realsense-driver` | `realsense_driver` | `open-pi-realsense-driver` | yes |
| `fusion` | `sensor-fusion`, `open-pi-sensor-fusion` | `open-pi-sensor-fusion` | `open-pi-sensor-fusion` | yes |
| `slam` | `mapping`, `localization`, `open-pi-slam` | `slam` | `robot-slam` | yes |
| `voice` | `tts`, `voice-ia`, `open-pi-voice-ia` | `open-pi-voice-ia` | `open-pi-voice-ia` | yes |
| `robot` | `main`, `bringup`, `open_pi_robot`, `open-pi-robot` | `open_pi_robot` | `open-pi-robot` | yes |
| `teleoperation` | `joystick`, `open-pi-joystick` | `open-pi-joystick` | `open-pi-joystick` | no |

`enabled: false` keeps a component visible in `list`, but excludes it from both
default and explicit selection. Selecting it is an argument/configuration error.

## Hardware checks

Hardware is checked during default startup, `create`, `start`, `restart`, and
`check`. `build` deliberately performs no hardware check.

| Component | Declared check |
| --- | --- |
| `stm32` | A path matches `/dev/ttyACM*` |
| `lidar` | A path matches `/dev/ttyUSB*` |
| `realsense` | `lsusb` reports `8086:0b3a` |
| `voice` | `/dev/snd` is a directory |
| `teleoperation` | A path matches `/dev/input/js*` |
| `slam=toolbox` | A path matches `/dev/ttyUSB*` |
| `slam=rtab` | `lsusb` reports `8086:0b3a` |

The supported generic check types are:

- `glob`, with a `pattern`;
- `directory`, with a `path`;
- `usb`, with four-digit hexadecimal `vid` and `pid` values.

A component and its selected variant may each declare checks. Every referenced
check must pass. These checks prove host discovery only, not sensor health,
permissions inside the container, ROS publication, calibration, or data quality.

## SLAM variants

RTAB-Map remains the default SLAM variant. The generic variant syntax and all
legacy selectors are equivalent:

```bash
./Open-PiRobot.sh create slam --variant slam=toolbox
./Open-PiRobot.sh create slam --slam_toolbox

./Open-PiRobot.sh create slam --variant slam=rtab
./Open-PiRobot.sh create slam --slam__rtab
./Open-PiRobot.sh create slam --slam_rtab
```

Variant aliases, checks, and the `SLAM_PACKAGE`, `SLAM_LAUNCH_FILE`, and
`SLAM_CONFIG_FILE` overrides live in `config/robot.yaml`. Overrides are added
only to subprocesses for the `slam` component; other components receive the
unchanged manager environment. Selecting two different variants for one module
is rejected before any Docker command runs.

Changing the backend requires `create` or `restart`. A plain `start` reuses the
command stored in the existing container, so pass the matching variant to make
the manager check the correct hardware prerequisite.

## Registry schema

The top-level registry fields are `version`, `hardware_checks`, and `modules`.
Module order defines default execution order. Module defaults are:

```yaml
enabled: true
default_selected: true
required: false
aliases: []
checks: []
```

Modules require `compose`, `service`, and `container`. Their Compose paths are
always relative to the Open-PiRobot project root, including when `--config`
points to a registry elsewhere. Paths may contain spaces. A module with variants
also declares `default_variant`; each variant may provide `aliases`,
`environment`, and `checks`.

Configuration loading is safe and strict. Before Docker use, the manager rejects
duplicate YAML keys, unknown fields, wrong types, ambiguous or reserved aliases,
unknown check/variant references, invalid VID/PID values, and paths that are
absolute or escape the project root.

Use an alternate registry without changing the project default:

```bash
./Open-PiRobot.sh --config /tmp/robot-lab.yaml validate-config
./Open-PiRobot.sh --config /tmp/robot-lab.yaml build sensor-test
```

`validate-config` checks every enabled component's Compose path without querying
the Docker daemon and without touching hardware.

## Adding a component

Assume a new module already provides `modules/status_display/compose.yaml` with
service `status-display` and container `open-pi-status-display`. If it uses only
supported checks, adding it requires no Python change:

```yaml
version: 1

hardware_checks:
  display_port:
    type: glob
    pattern: /dev/ttyDISPLAY*
    message: No status display was found.

modules:
  # Existing entries remain in their desired execution order.

  status_display:
    compose: modules/status_display/compose.yaml
    service: status-display
    container: open-pi-status-display
    aliases: [display]
    default_selected: false
    checks: [display_port]
```

Then validate and use it:

```bash
./Open-PiRobot.sh validate-config
./Open-PiRobot.sh build display
./Open-PiRobot.sh create status_display
```

The Compose file remains the source for image, build context, mounts, devices,
environment, and container command. A new hardware-check type requires an
isolated implementation in `scripts/robot_manager/hardware.py` plus tests.

The runtime registry and Git submodules solve different problems. A registry
entry makes an already present Compose project manageable. It does not add a
Git submodule, initialize one, select its revision, or update it; those remain
explicit Git operations outside the manager.

## Required and optional failures

`stm32` is marked `required: true`. Its missing hardware, invalid Compose model,
or failed operation stops the command with status `1`. Other registered modules
are optional by default: a failure emits a warning, skips that component, and
allows later components to run. A completed command with optional skips returns
status `0`.

Exit statuses are:

- `0`: completed, including optional components that were skipped;
- `1`: global Docker failure or required-component operational failure;
- `2`: command-line or registry error.

If the enabled default group is empty, selection fails with status `2` before
Docker is queried.

## Environment and logging

The inherited environment is preserved for every subprocess. Common overrides
include:

```bash
ROS_DOMAIN_ID=7 ./Open-PiRobot.sh create stm32 robot
ROBOT_PLATFORM=linux/amd64 ./Open-PiRobot.sh build
BUILD_JOBS=1 ./Open-PiRobot.sh build realsense
```

Terminal output is appended by severity to:

```text
script_logs/debug_info.txt
script_logs/warnings_errors.txt
```

Normal subprocess output follows stdout and error output follows stderr. The
`logs` command starts one direct `docker logs` subprocess per selected container,
prefixes its output with the component name, and terminates each process group
on `SIGINT` or `SIGTERM` so log descendants are not left running.

Return to the [project README](../README.md) for system architecture, ROS
interfaces, TF ownership, and deployment guidance.
