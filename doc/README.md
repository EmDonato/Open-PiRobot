# Open-PiRobot Container Manager

`Open-PiRobot.sh` is the central command used to build, create, start, stop,
inspect, and remove the containers that make up Open-PiRobot.

Run every command from the repository root:

```bash
./Open-PiRobot.sh [COMMAND] [CONTAINER ...] [SLAM OPTION]
```

## Default behavior

Running the script without arguments manages the complete robot:

```bash
./Open-PiRobot.sh
```

Targets are processed in this order:

```text
stm32 -> lidar -> realsense -> fusion -> slam -> voice -> robot
```

For every target, the manager:

1. Verifies Docker, Docker Compose, and the target's Compose configuration.
2. Checks runtime hardware when the target requires a host device.
3. Checks whether the named container already exists.
4. Builds the image only when the container is missing.
5. Creates and starts a missing container.
6. Reconciles an existing container with the current Compose configuration
   without rebuilding its image.
7. Verifies that the container is running.

This behavior is idempotent: running the script again does not intentionally
rebuild images for containers that already exist. Use `create` when you want to
build again and apply a new image.

## Commands

| Command | Aliases | Behavior |
| --- | --- | --- |
| `build` | `--build` | Builds images without requiring connected hardware or creating containers |
| `create` | `-c`, `--create` | Checks hardware, builds images, and creates or recreates containers in detached mode |
| `start` | `-s`, `--start` | Starts existing containers; it does not create missing containers |
| `stop` | `-t`, `--stop` | Stops existing containers without removing them |
| `restart` | `-r`, `--restart` | Checks hardware and recreates existing containers with the current image and configuration |
| `remove` | `-x`, `--remove` | Stops and removes containers but keeps their images |
| `status` | `--status` | Shows whether each selected container is running, exited, or not created |
| `check` | `--check` | Validates Compose files and host hardware prerequisites |
| `logs` | `--logs` | Follows the last 50 log lines and new output from selected containers |
| `help` | `-h`, `--help` | Prints the built-in command reference |

When a command is provided without a target list, it applies to all targets.

```bash
./Open-PiRobot.sh build
./Open-PiRobot.sh status
./Open-PiRobot.sh stop
```

## Targets and aliases

| Canonical target | Accepted aliases | Compose service | Container name |
| --- | --- | --- | --- |
| `stm32` | `stm32_driver`, `open-pi-stm32-driver` | `stm32_driver` | `open-pi-stm32-driver` |
| `lidar` | `lidar_driver`, `open-pi-lidar-driver` | `lidar_driver` | `open-pi-lidar-driver` |
| `realsense` | `camera`, `realsense_driver`, `open-pi-realsense-driver` | `realsense_driver` | `open-pi-realsense-driver` |
| `fusion` | `sensor-fusion`, `open-pi-sensor-fusion` | `open-pi-sensor-fusion` | `open-pi-sensor-fusion` |
| `slam` | `mapping`, `localization`, `open-pi-slam` | `slam` | `robot-slam` |
| `voice` | `tts`, `voice-ia`, `open-pi-voice-ia` | `open-pi-voice-ia` | `open-pi-voice-ia` |
| `robot` | `main`, `bringup`, `open_pi_robot`, `open-pi-robot` | `open_pi_robot` | `open-pi-robot` |

Use `all` to explicitly select every target. Repeated target names are removed
from the selection.

```bash
./Open-PiRobot.sh restart all
./Open-PiRobot.sh build voice voice lidar
```

## Selecting containers

Place the command first and then list one or more targets:

```bash
./Open-PiRobot.sh --build voice lidar
./Open-PiRobot.sh create stm32 robot
./Open-PiRobot.sh create slam --slam_toolbox
./Open-PiRobot.sh start fusion slam --slam__rtab
./Open-PiRobot.sh stop realsense
./Open-PiRobot.sh restart stm32
./Open-PiRobot.sh remove voice
./Open-PiRobot.sh status robot stm32
./Open-PiRobot.sh logs stm32 lidar
```

An unknown command or target prints the help text and exits without performing
container operations.

## Prerequisite checks

Hardware checks are performed by the default workflow and by `create`,
`start`, `restart`, and `check`. A plain image build does not require hardware
to be connected.

| Target | Check |
| --- | --- |
| `stm32` | At least one `/dev/ttyACM*` device exists |
| `lidar` | At least one `/dev/ttyUSB*` device exists |
| `realsense` | `lsusb` reports USB ID `8086:0b3a` |
| `slam` with `--slam_toolbox` | At least one `/dev/ttyUSB*` LiDAR device exists |
| `slam` with `--slam__rtab` | `lsusb` reports RealSense USB ID `8086:0b3a` |
| `voice` | The `/dev/snd` directory exists |
| `fusion` | No dedicated host hardware prerequisite |
| `robot` | No dedicated host hardware prerequisite |

The checks confirm device discovery, not full device functionality. A device
can still fail inside its container because of permissions, an incorrect port
in a parameter file, firmware, or another process using it.

## SLAM selection

The `robot-slam` image contains SLAM Toolbox and RTAB-Map. Select exactly one
mode whenever the `slam` target is created, recreated, checked, or started:

| Option | Backend | Required hardware |
| --- | --- | --- |
| `--slam_toolbox` | SLAM Toolbox 2D mapping | LiDAR at `/dev/ttyUSB*` |
| `--slam__rtab` | RTAB-Map RGB-D mapping (default) | RealSense D435i `8086:0b3a` |
| `--slam_rtab` | Alias for `--slam__rtab` | RealSense D435i `8086:0b3a` |

The options may appear anywhere in the command and are mutually exclusive:

```bash
./Open-PiRobot.sh create slam --slam_toolbox
./Open-PiRobot.sh restart slam --slam__rtab
./Open-PiRobot.sh check stm32 lidar fusion robot slam --slam_toolbox
```

When starting an existing SLAM container, pass the selector used when it was
created so the manager validates the correct sensor:

```bash
./Open-PiRobot.sh start slam --slam_toolbox
```

Changing the algorithm requires `create` or `restart`, because `start` retains
the command stored in the existing container. Only one backend may run because
both can publish `map -> odom`.

## Required and optional targets

STM32 is treated as the required safety-critical target:

- A missing STM32 device is an error.
- A missing or invalid STM32 Compose file is an error.
- A failed STM32 Docker operation is an error.
- The manager stops immediately and returns a non-zero status.

All other targets are optional. A failed optional target produces a warning,
is skipped, and processing continues with the next target. The command can
therefore complete successfully even when one or more optional devices are not
connected.

This policy applies only to selected targets. For example, the following
command can build the voice image without selecting or checking STM32:

```bash
./Open-PiRobot.sh build voice
```

## Progress and logs

The manager displays one progress bar per selected target:

```text
[##########----------] 50% (1/2) voice
[####################] 100% (2/2) lidar
```

Terminal output remains visible while persistent output is separated by
severity:

```text
script_logs/debug_info.txt
script_logs/warnings_errors.txt
```

- `debug_info.txt` receives `DEBUG`, `INFO`, and `OK` messages, progress bars,
  status tables, help text, and normal command output.
- `warnings_errors.txt` receives `WARNING` and `ERROR` messages together with
  command output written to stderr.

Both files are created automatically and excluded from Git. They are not
cleared between commands, which preserves the history of manager operations.

The `logs` command is different: it opens live Docker log streams and remains
active until interrupted with `Ctrl+C`.

```bash
./Open-PiRobot.sh logs stm32
./Open-PiRobot.sh logs fusion robot
```

When following all logs, an absent STM32 container triggers the mandatory
STM32 error policy. Select only the desired optional target if STM32 has not
been created yet.

## Exit behavior

- Exit status `0` indicates that the requested operation completed. Optional
  targets may still have produced warnings.
- Exit status `1` indicates a global Docker failure or a mandatory STM32
  failure.
- Exit status `2` indicates invalid command syntax or an unknown target.
- Interrupting live logs can return the shell's interruption status.

Always inspect warning lines or `script_logs/warnings_errors.txt`; a successful
exit status does not mean that every optional module was available.

## Environment variables

Environment variables are passed naturally to the individual Compose files:

```bash
ROS_DOMAIN_ID=7 ./Open-PiRobot.sh create stm32 robot
ROBOT_PLATFORM=linux/amd64 ./Open-PiRobot.sh build stm32 lidar realsense slam
BUILD_JOBS=1 ./Open-PiRobot.sh build realsense
```

| Variable | Default | Used by |
| --- | --- | --- |
| `ROS_DOMAIN_ID` | `0` | Every container |
| `ROBOT_PLATFORM` | `linux/arm64` | STM32, LiDAR, RealSense, and SLAM |
| `HOST_UID` | `1000` | Supported driver image builds |
| `HOST_GID` | `1000` | Supported driver image builds |
| `INTERFACES_CONTEXT` | `../../interfaces` | STM32 build context |
| `LIBREALSENSE_REF` | `v2.56.5` | RealSense build |
| `REALSENSE_ROS_REF` | `4.56.4` | RealSense ROS build |
| `BUILD_JOBS` | `2` | RealSense build |

Use the same `ROS_DOMAIN_ID` for every module that should communicate through
ROS 2.

## Typical workflows

### First robot startup

Choose one SLAM path. For SLAM Toolbox:

```bash
git submodule update --init --recursive
./Open-PiRobot.sh check stm32 lidar fusion robot slam --slam_toolbox
./Open-PiRobot.sh create stm32 lidar fusion robot slam --slam_toolbox
./Open-PiRobot.sh status
```

For RTAB-Map, replace `lidar` with `realsense` and use `--slam__rtab`.

### Rebuild one changed module

```bash
./Open-PiRobot.sh create fusion
./Open-PiRobot.sh logs fusion
```

`create` includes an image build and allows Compose to recreate the selected
container with the new image.

### Stop the robot without deleting containers

```bash
./Open-PiRobot.sh stop
```

### Remove selected containers

```bash
./Open-PiRobot.sh remove voice slam
```

Images are preserved, so a later `create` can reuse cached build layers.

## Troubleshooting

### Docker daemon is not reachable

Confirm that Docker is running and that the current user can access it:

```bash
docker info
docker compose version
```

### STM32 is not detected

Check the host device and compare it with
`drivers/Ros2_stm32_driver/config/params.yaml`:

```bash
ls -l /dev/ttyACM*
```

The default node configuration expects `/dev/ttyACM0` at 115200 baud.

### An optional module is skipped

Run its check and inspect the persistent logs:

```bash
./Open-PiRobot.sh check <target>
./Open-PiRobot.sh status <target>
./Open-PiRobot.sh logs <target>
```

Also inspect the target's `config/params.yaml` or other configuration files.

### A container exits immediately

Follow only that container's output:

```bash
./Open-PiRobot.sh logs <target>
```

Common causes are host-device permissions, an incorrect serial or audio device,
ROS parameter errors, and mismatched architectures.

Return to the [main project README](../README.md) for the project architecture,
dependencies, and Quick Start.

## Architecture decisions

- [ADR-001: Deploy robot capabilities as independent ROS 2 containers](ADR-001-containerized-modules.md)
- [ADR-002: Provide one hardware-gated, selectable SLAM runtime](ADR-002-selectable-slam-backends.md)
