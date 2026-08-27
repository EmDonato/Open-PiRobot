# Open-PiRobot

Open-PiRobot is a modular ROS 2 robot stack designed around independent Docker
containers. Hardware drivers, control modules, voice output, and the main robot
description can be built and operated separately while communicating through
ROS 2 over the host network.

The project currently targets ROS 2 Humble on Ubuntu 22.04 and is intended to
run on a Raspberry Pi 5. Driver images default to `linux/arm64`, but they can
also be built on an x86-64 development machine.

## Features

- Independent containers for each hardware driver and robot module.
- ROS 2 communication through Cyclone DDS and a shared `ROS_DOMAIN_ID`.
- Central container management through `Open-PiRobot.sh`.
- Automatic creation and startup of missing containers.
- Mandatory STM32 controller validation and non-blocking warnings for optional
  hardware.
- URDF/Xacro robot description published by `robot_state_publisher`.
- Differential-drive sensor fusion, joystick teleoperation, RealSense camera,
  LD06 LiDAR, and Piper text-to-speech support.

## Architecture

Each component has its own Dockerfile and Compose project. All runtime
containers use host networking so ROS 2 discovery works without exposing
individual ports.

| Target | Container | Responsibility | Host hardware |
| --- | --- | --- | --- |
| `robot` | `open-pi-robot` | Runs `open_pi_bringup` and publishes the robot description and transforms | None |
| `stm32` | `open-pi-stm32-driver` | Communicates with the STM32 motor and sensor controller | `/dev/ttyACM*` (required) |
| `lidar` | `open-pi-lidar-driver` | Publishes LD06 laser scans | `/dev/ttyUSB*` |
| `realsense` | `open-pi-realsense-driver` | Publishes Intel RealSense D435i color and depth data | USB device `8086:0b3a` |
| `fusion` | `open-pi-sensor-fusion` | Fuses IMU and encoder measurements into odometry | None |
| `joystick` | `open-pi-joystick` | Runs joystick input, teleoperation, and control-button nodes | `/dev/input/js*` |
| `voice` | `open-pi-voice-ia` | Converts messages from `assistant/response` to speech with Piper | `/dev/snd` |

The STM32 driver is the only mandatory runtime component. If its validation or
Docker operation fails, the central manager stops with an error. Other missing
devices or failed optional modules produce warnings and do not prevent the
remaining components from being processed.

## Repository layout

```text
Open-PiRobot/
├── docker/                         Main robot image and entrypoint
├── src/
│   ├── open_pi_bringup/            Main ROS 2 launch package
│   └── robot_descriptor/           URDF, Xacro, meshes, and simulation files
├── interfaces/                     Shared ROS 2 messages and services
├── drivers/
│   ├── Ros2_stm32_driver/          STM32 serial driver
│   ├── Ros2_lidar_driver/          LD06 serial LiDAR driver
│   └── Ros2_realsense_driver/      RealSense D435i driver
├── modules/
│   ├── Ros2_sensor_fusion/         Differential-drive EKF
│   ├── Ros2_tts_voice/             Piper text-to-speech node
│   ├── teleoperation/              Joystick control stack
├── doc/README.md                   Container-manager documentation
├── compose.yaml                    Main robot Compose file
└── Open-PiRobot.sh                 Central management command
```

The directories under `drivers/` and `modules/` are maintained as Git
submodules. Initialize them before building the project.

## Dependencies

### Host software

- A 64-bit Linux host. Raspberry Pi OS/Ubuntu on Raspberry Pi 5 is the primary
  deployment target.
- Git with submodule support.
- Docker Engine with a running Docker daemon.
- Docker Compose v2, available through the `docker compose` command.
- `usbutils` and its `lsusb` command for RealSense prerequisite checks.
- Internet access during the first image build. Some images download system
  packages, RealSense sources, Piper, and the voice model.
- Permission for the current user to access Docker and the required host
  devices.

ROS 2 does not need to be installed on the host because ROS 2 Humble and the
required packages are installed inside the images.

### Hardware

- STM32 Nucleo F303RE robot controller exposed as `/dev/ttyACM0` by default.
- LDROBOT LD06 LiDAR exposed as `/dev/ttyUSB0` when the LiDAR module is used.
- Intel RealSense D435i when the camera module is used.
- Linux-compatible joystick when teleoperation is used.
- ALSA-compatible audio output when text-to-speech is used.

The driver containers use privileged device access and mount the relevant host
device trees. Verify permissions and udev rules on the host before startup.

## Quick Start

1. Clone the repository and initialize every submodule:

   ```bash
   git clone --recurse-submodules <repository-url> Open-PiRobot
   cd Open-PiRobot
   git submodule update --init --recursive
   ```

2. Make sure Docker is available to the current user:

   ```bash
   docker info
   docker compose version
   ```

3. Connect the STM32 controller and any optional devices, then check the
   prerequisites:

   ```bash
   ./Open-PiRobot.sh check
   ```

4. Build missing images, create missing containers, and start the robot:

   ```bash
   ./Open-PiRobot.sh
   ```

   The first run can take a long time, especially while building the RealSense
   image. Later runs reuse existing images and containers.

5. Inspect the resulting state or follow logs:

   ```bash
   ./Open-PiRobot.sh status
   ./Open-PiRobot.sh logs stm32
   ```

To build on an x86-64 machine instead of the default ARM64 platform, export the
platform before running the manager:

```bash
export ROBOT_PLATFORM=linux/amd64
./Open-PiRobot.sh build
```

## Common operations

Commands apply to all targets when no target list is supplied:

```bash
./Open-PiRobot.sh build
./Open-PiRobot.sh start
./Open-PiRobot.sh stop
./Open-PiRobot.sh restart
./Open-PiRobot.sh status
```

Pass one or more target names to operate only on those containers:

```bash
./Open-PiRobot.sh --build stm32 lidar
./Open-PiRobot.sh create robot fusion
./Open-PiRobot.sh restart voice
./Open-PiRobot.sh logs robot stm32
```

See [doc/README.md](doc/README.md) for the complete command reference,
selection rules, aliases, logging behavior, and error handling.

## Runtime configuration

The most useful environment variables are:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ROS_DOMAIN_ID` | `0` | ROS 2 discovery domain shared by all containers |
| `ROBOT_PLATFORM` | `linux/arm64` | Platform for STM32, LiDAR, and RealSense images |
| `HOST_UID` | `1000` | User ID passed to supported driver image builds |
| `HOST_GID` | `1000` | Group ID passed to supported driver image builds |
| `INTERFACES_CONTEXT` | `../../interfaces` | Shared interface build context for the STM32 image |
| `LIBREALSENSE_REF` | `v2.56.5` | librealsense source version |
| `REALSENSE_ROS_REF` | `4.56.4` | RealSense ROS wrapper source version |
| `BUILD_JOBS` | `2` | Parallel jobs used by the RealSense source build |

ROS node parameters are stored in each component's `config/` directory. The
driver Compose files mount those directories read-only into their containers.
Restart the affected container after changing runtime parameters.

## Main bringup

The main container starts:

```bash
ros2 launch open_pi_bringup robot_launch.py
```

The launch file expands the robot Xacro description and starts
`robot_state_publisher` with real-time operation (`use_sim_time: false`). The
description package also contains meshes, a Gazebo world, and simulation
configuration for future simulation workflows.

## Logs and troubleshooting

Every manager invocation remains visible in the terminal. Output is also split
by severity between two persistent files:

```text
script_logs/debug_info.txt
script_logs/warnings_errors.txt
```

The first file contains debug, informational, successful, progress, and normal
command output. The second contains warnings, errors, and stderr output.

Useful diagnostics:

```bash
./Open-PiRobot.sh check
./Open-PiRobot.sh status
./Open-PiRobot.sh logs <target>
```

If Docker cannot be reached, verify that the daemon is running and that the
current user has access to its socket. If a hardware module is skipped, verify
its device path on the host and compare it with the corresponding YAML file in
the module's `config/` directory.

This repository is under active development. Package metadata and licensing
information should be reviewed before distribution.
