# Open-PiRobot

Open-PiRobot is a modular ROS 2 Jazzy stack for a Raspberry Pi 5 mobile
robot. Hardware drivers, state estimation, SLAM, voice output, and robot
description run in separate Docker containers and communicate through Cyclone
DDS on the host network.

The central [`Open-PiRobot.sh`](Open-PiRobot.sh) command builds and manages the
runtime. It can start either SLAM Toolbox with the LiDAR or RTAB-Map with the
RealSense camera, and it prevents the selected SLAM container from starting
when its required sensor is not detected.

## Quickstart

### 1. Prepare the host

You need a 64-bit Linux host with:

- Git and a GitHub SSH key, because the submodule URLs use SSH;
- Python 3.10 or newer and PyYAML (`python3` and `python3-yaml` on Ubuntu);
- Docker Engine and Docker Compose v2;
- `usbutils` (`lsusb`) for RealSense detection;
- permission to access Docker and the connected USB, serial, input, and audio
  devices.

ROS 2 does not need to be installed on the host.

Verify Docker:

```bash
sudo apt install python3 python3-yaml
docker info
docker compose version
```

### 2. Clone the complete project

```bash
git clone --branch jazzy-migration --recurse-submodules git@github.com:EmDonato/Open-PiRobot.git
cd Open-PiRobot
git submodule update --init --recursive
```

If the repository was already cloned, update it together with every
submodule:

```bash
git fetch origin
git switch jazzy-migration
git pull --ff-only --recurse-submodules=on-demand origin jazzy-migration
git submodule sync --recursive
git submodule update --init --recursive
```

Save any local changes in the root and submodules before switching branches.
The submodule update checks out the exact commits recorded by the root;
do not use `--remote` to deploy this migration.

### 3. Select the build platform

Images default to Raspberry Pi 5 (`linux/arm64`). On an x86-64 development
machine, prefix manager commands with:

```bash
export ROBOT_PLATFORM=linux/amd64
```

Do not set this override on the Raspberry Pi unless a different target is
intentional.

Build on the development PC without starting services or requiring hardware:

```bash
ROBOT_PLATFORM=linux/amd64 ./Open-PiRobot.sh build
ROBOT_PLATFORM=linux/amd64 ./Open-PiRobot.sh build teleoperation
```

See [Jazzy migration evidence](docs/MIGRATION_HUMBLE_TO_JAZZY.md) for validation
results and the remaining Raspberry Pi acceptance checks.

### 4. Connect the required hardware

The STM32 controller is mandatory and must appear as `/dev/ttyACM*`.

Then choose one mapping stack:

| Mapping mode | Required sensor | Host detection | Selector |
| --- | --- | --- | --- |
| SLAM Toolbox (2D) | LD06 LiDAR | `/dev/ttyUSB*` | `--slam_toolbox` |
| RTAB-Map (RGB-D) | RealSense D435i | USB ID `8086:0b3a` | `--slam__rtab` |

### 5. Check and start a minimal mapping stack

For SLAM Toolbox:

```bash
./Open-PiRobot.sh check stm32 lidar fusion robot slam --slam_toolbox
./Open-PiRobot.sh create stm32 lidar fusion robot slam --slam_toolbox
```

For RTAB-Map:

```bash
./Open-PiRobot.sh check stm32 realsense fusion robot slam --slam__rtab
./Open-PiRobot.sh create stm32 realsense fusion robot slam --slam__rtab
```

The first `create` builds the selected images and can take a long time,
especially for RealSense. Later `start` commands reuse the existing
containers; pass the same SLAM selector so the manager checks the correct
sensor. `--slam_rtab` is accepted as an alias for `--slam__rtab`.

> **RTAB-Map data warning:** the current
> `modules/Ros2_slam_module/config/slam.yaml` defaults to `reset_mapping`.
> Starting RTAB-Map in this mode deletes the existing `/data/rtabmap.db`.
> Change the mode to `mapping` before relying on database persistence.

### 6. Verify the runtime

```bash
./Open-PiRobot.sh status
./Open-PiRobot.sh logs slam
```

Useful ROS checks from a ROS 2 shell on the same `ROS_DOMAIN_ID` include:

```bash
ros2 topic hz /scan                         # SLAM Toolbox input
ros2 topic hz /odom                         # EKF output
ros2 run tf2_ros tf2_echo odom base_link
```

For RTAB-Map, also verify the RGB, aligned-depth, and camera-info topic names
published by the RealSense container. They must match the names configured in
`modules/Ros2_slam_module/config/slam.yaml`.

To manage every central target at once, run:

```bash
./Open-PiRobot.sh --slam_toolbox
# or
./Open-PiRobot.sh --slam__rtab
```

The manager skips unavailable optional hardware with a warning. A missing
STM32 stops the operation with an error.

## System architecture

Each runtime concern has its own image and Compose service. All containers use
host networking and the same `ROS_DOMAIN_ID`, allowing ROS 2 discovery without
maintaining a list of Docker port mappings.

| Manager target | Container | Responsibility | Runtime prerequisite |
| --- | --- | --- | --- |
| `stm32` | `open-pi-stm32-driver` | Motor-control bridge, IMU, wheel data, joint states, and control service | `/dev/ttyACM*`; mandatory |
| `lidar` | `open-pi-lidar-driver` | LD06 `sensor_msgs/msg/LaserScan` publisher | `/dev/ttyUSB*` |
| `realsense` | `open-pi-realsense-driver` | D435i RGB and aligned-depth publisher | USB `8086:0b3a` |
| `fusion` | `open-pi-sensor-fusion` | EKF odometry and `odom -> base_link` TF | ROS inputs from STM32/control |
| `slam` | `robot-slam` | SLAM Toolbox or RTAB-Map | LiDAR for Toolbox; RealSense for RTAB |
| `voice` | `open-pi-voice-ia` | Piper text-to-speech | `/dev/snd` |
| `robot` | `open-pi-robot` | Xacro expansion and `robot_state_publisher` | None |
| `teleoperation` | `open-pi-joystick` | Joystick input and velocity commands | `/dev/input/js*` |

Teleoperation is centrally manageable but intentionally excluded from the
default group. Select it explicitly with `teleoperation`, `joystick`, or
`open-pi-joystick`.

The major runtime relationships are:

```text
STM32 ---- IMU + encoder velocity ----> sensor fusion ----> /odom + odom->base_link
  ^                                              |
  |                                              +----> SLAM Toolbox or RTAB-Map
  +---------------- /cmd_vel --------------------+

LiDAR ---------------- /scan ---------------------------> SLAM Toolbox
RealSense -------- RGB + aligned depth + camera info ---> RTAB-Map
robot_state_publisher -------- static robot TF ---------> all consumers
```

Only one SLAM backend must run at a time because both own the `map -> odom`
transform.

## SLAM modes

The SLAM image contains both backends. The central manager exports the package,
launch file, and configuration selected by the command-line option.

| Property | SLAM Toolbox | RTAB-Map |
| --- | --- | --- |
| Selector | `--slam_toolbox` | `--slam__rtab` (default) |
| Primary input | `/scan` | RGB, aligned depth, camera info, `/odom` |
| Robot frame | `base_footprint` | `base_link` |
| Map product | 2D occupancy map and pose graph | 2D/3D RGB-D map and database |
| Configuration | `config/slam_toolbox_config.yaml` | `config/slam.yaml` |
| Persistent data | Save/serialize explicitly under `/data` | `/data/rtabmap.db` |

The manager checks physical host devices before default startup, `create`,
`start`, and `restart`. Image-only `build` operations do not require connected
hardware.

## Repository layout

```text
Open-PiRobot/
├── Open-PiRobot.sh                 Thin Python manager wrapper
├── config/robot.yaml               Runtime component registry
├── scripts/robot_manager/          Manager implementation
├── compose.yaml                    Robot-description service
├── docker/                         Main image and entrypoint
├── interfaces/                     Shared ROS messages and services
├── src/
│   ├── open_pi_bringup/            Main launch package
│   └── robot_descriptor/           Xacro, URDF assets, and simulation config
├── drivers/
│   ├── Ros2_stm32_driver/          STM32 serial bridge
│   ├── Ros2_lidar_driver/          LD06 serial driver
│   └── Ros2_realsense_driver/      RealSense ROS wrapper
├── modules/
│   ├── Ros2_sensor_fusion/         Differential-drive EKF
│   ├── Ros2_slam_module/           Toolbox and RTAB-Map bringup
│   ├── Ros2_tts_voice/             Piper text-to-speech
│   └── teleoperation/              Joystick and velocity control
└── docs/
    ├── README.md                   Manager reference
    ├── ADR-001-containerized-modules.md
    └── ADR-002-selectable-slam-backends.md
```

Drivers and modules are Git submodules. A leading `-` in
`git submodule status --recursive` means that a submodule still needs to be
initialized. A leading `+` means that its checkout differs from the commit
recorded by the parent repository.

## Container manager

General syntax:

```bash
./Open-PiRobot.sh [--config PATH] [COMMAND] [TARGET ...] [VARIANT]
```

| Command | Aliases | Effect |
| --- | --- | --- |
| `build` | `--build` | Build images without checking hardware |
| `create` | `-c`, `--create` | Build, create, and start selected containers |
| `start` | `-s`, `--start` | Start containers that already exist |
| `stop` | `-t`, `--stop` | Stop selected containers |
| `restart` | `-r`, `--restart` | Recreate existing containers with the current image/configuration |
| `remove` | `-x`, `--remove` | Stop and remove containers, preserving images and bind-mounted data |
| `status` | `--status` | Show container state |
| `check` | `--check` | Validate Docker, Compose, and hardware prerequisites |
| `logs` | `--logs` | Follow the last 50 lines and new container output |
| `list` | — | Show registered components, aliases, enablement, and default membership |
| `validate-config` | — | Validate the registry and enabled Compose paths without Docker or hardware |

Examples:

```bash
./Open-PiRobot.sh build fusion slam
./Open-PiRobot.sh restart stm32 robot
./Open-PiRobot.sh stop
./Open-PiRobot.sh remove voice
./Open-PiRobot.sh logs stm32 fusion slam
./Open-PiRobot.sh build teleoperation
./Open-PiRobot.sh --variant slam=toolbox create slam
```

When no target list is supplied, the command applies to the enabled default
group. `all` selects that same group; teleoperation is not part of it.
See [`docs/README.md`](docs/README.md) for aliases, error policy, exit statuses,
and logging details.

## Configuration

The ordered runtime registry is [`config/robot.yaml`](config/robot.yaml).
It declares Compose paths, services, containers, aliases, required/optional
policy, hardware checks, default selection, and SLAM variants. Compose files
remain authoritative for images, mounts, devices, and container parameters.
Use `--config PATH` to test another registry; its Compose paths still resolve
relative to this project root.

All communicating containers must use the same DDS domain:

```bash
ROS_DOMAIN_ID=7 ./Open-PiRobot.sh create stm32 lidar fusion robot slam --slam_toolbox
```

Important environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ROS_DOMAIN_ID` | `0` | ROS 2 discovery domain shared by all containers |
| `ROBOT_PLATFORM` | `linux/arm64` | Target platform for all eight images |
| `HOST_UID` | `1000` | Container user ID for supported builds |
| `HOST_GID` | `1000` | Container group ID for supported builds |
| `INTERFACES_CONTEXT` | `../../interfaces` | Shared-interface context for the STM32 image |
| `LIBREALSENSE_REF` | `v2.56.5` | librealsense source version |
| `REALSENSE_ROS_REF` | `4.56.4` | RealSense ROS wrapper version |
| `BUILD_JOBS` | `2` | Parallel jobs for the RealSense source build |

Node parameters live in each component's `config/` directory. Most Compose
services mount configuration read-only, so restart or recreate the affected
container after changing parameters.

## ROS interfaces and TF ownership

Key project interfaces include:

- STM32 publishes `/imu`, `/enc/twist_meas`, `/odom/solo`, `/joint_states`,
  `/debug/imu`, and robot status; it subscribes to `/cmd_vel`.
- Sensor fusion consumes IMU and encoder data, publishes `/odom`, and owns
  `odom -> base_link`.
- The robot description owns fixed transforms beneath `base_link`, including
  the LiDAR, camera mount, chassis, and `base_footprint` relationships.
- The selected SLAM backend owns `map -> odom`.
- `robot_interfaces` defines `WheelSpeeds`, `ImuEuler`, and
  `ControlCommand`.

`/odom/solo` is encoder-only diagnostic odometry and does not publish TF. It
must not replace the fused odometry when SLAM is active.

## Logs and troubleshooting

Manager output remains visible and is also appended to:

```text
script_logs/debug_info.txt
script_logs/warnings_errors.txt
```

Start with:

```bash
./Open-PiRobot.sh check <target>
./Open-PiRobot.sh status <target>
./Open-PiRobot.sh logs <target>
```

Common checks:

```bash
ls -l /dev/ttyACM*                    # STM32
ls -l /dev/ttyUSB*                    # LiDAR
lsusb | grep -i 8086:0b3a             # RealSense D435i
docker compose version
docker info
```

If a container starts but ROS data is not visible, confirm that every process
uses the same `ROS_DOMAIN_ID`, the host firewall permits DDS traffic, and the
machines' clocks are synchronized. For SLAM failures, verify topic names,
message rates, and the complete TF chain before tuning mapping parameters.

## Documentation

- [`docs/README.md`](docs/README.md): complete container-manager reference.
- [`docs/ADR-001-containerized-modules.md`](docs/ADR-001-containerized-modules.md):
  container-per-module deployment, host networking, and DDS choice.
- [`docs/ADR-002-selectable-slam-backends.md`](docs/ADR-002-selectable-slam-backends.md):
  selectable SLAM backends and hardware-gated activation.
- Each driver and module has its own README with package-specific parameters,
  topics, and validation steps.

## Project status

The repository is under active development. Hardware checks establish device
presence, not sensor health, calibration, topic compatibility, or mapping
quality. Validate the full ROS graph and TF tree on the physical robot before
autonomous operation. Package metadata and licensing declarations also require
a final review before distribution.
