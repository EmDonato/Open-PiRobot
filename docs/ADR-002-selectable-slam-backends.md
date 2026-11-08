# ADR-002: Provide one hardware-gated, selectable SLAM runtime

- **Status:** Accepted
- **Date:** 2026-09-28
- **Decision owners:** Open-PiRobot maintainers
- **Scope:** SLAM algorithm selection, sensor prerequisites, TF ownership, and
  persistent mapping data

## Context

The robot has two mapping sensors with different strengths:

- the LD06 provides planar laser scans suitable for efficient 2D mapping with
  SLAM Toolbox;
- the RealSense D435i provides aligned RGB-D observations suitable for
  RTAB-Map and richer 2D/3D map products.

These algorithms need different topics, frames, parameters, and persistence
workflows. They both normally publish `map -> odom`, so running them together
would create conflicting TF authorities. Maintaining two unrelated SLAM
containers would also duplicate common ROS 2, configuration, lifecycle, and
data-mount logic.

The central manager can detect the physical sensors before starting modules,
but sensor presence alone does not prove the ROS inputs or TF chain are valid.

## Decision

Build SLAM Toolbox and RTAB-Map into one SLAM image and run exactly one backend
in the `robot-slam` container.

The central manager exposes these selectors:

| Selector | Backend | Required host sensor | Launch configuration |
| --- | --- | --- | --- |
| `--slam_toolbox` | SLAM Toolbox | LiDAR at `/dev/ttyUSB*` | `slam_toolbox_bringup/slam_toolbox_online_async.launch.py` with `config/slam_toolbox_config.yaml` |
| `--slam__rtab` | RTAB-Map | RealSense D435i USB `8086:0b3a` | `rtabmap_bringup/slam.launch.py` with `config/slam.yaml` |

`--slam_rtab` is an accepted spelling alias. RTAB-Map is the default when no
selector is supplied. The two selectors are mutually exclusive.

The manager exports the selected ROS package, launch file, and configuration
path into Compose. Hardware checks apply before default startup, `create`,
`start`, and `restart`; image-only builds remain possible without sensors.

Use these ownership and integration rules:

1. Only one SLAM backend runs at a time.
2. The EKF owns `odom -> base_link`.
3. The robot description supplies fixed sensor and body transforms.
4. The selected SLAM backend exclusively owns `map -> odom`.
5. SLAM Toolbox consumes `/scan` and uses `base_footprint` by default.
6. RTAB-Map consumes RGB, aligned depth, camera calibration, and `/odom`, and
   uses `base_link` by default.
7. The module's `data/` directory is mounted at `/data`. RTAB-Map stores its
   database there; SLAM Toolbox persistence must be requested through its
   save/serialization interfaces using a path under `/data`.

## Rationale

Runtime selection lets the same robot software support a low-cost 2D mapping
mode and an RGB-D mapping mode without allowing two map-frame publishers. One
image avoids duplicating the common base environment, entrypoint, data mount,
and Compose service.

Hardware gating catches the most common operator error before container
creation: selecting an algorithm whose physical sensor is not connected. The
check remains intentionally lightweight so image builds and CI do not require
robot hardware.

## Alternatives considered

### Always run both SLAM algorithms

Rejected because both can publish `map -> odom`, compute and memory usage would
increase, and two independent maps create ambiguous downstream behavior.

### Use only SLAM Toolbox

Rejected because it cannot use the available RGB-D stream to provide the map
products and visual loop closures available from RTAB-Map.

### Use only RTAB-Map

Rejected because the LiDAR path offers a simpler and typically lighter 2D
mapping mode when the camera is unavailable or unnecessary.

### Maintain a separate image and container for each backend

Rejected for the current project because common dependencies and lifecycle
logic would be duplicated. Separate images may become appropriate if image
size, build time, or backend release cadence becomes operationally costly.

### Select the backend automatically from whichever sensor is detected

Rejected because both sensors may be connected. Silent automatic selection
would make map type, CPU load, persistence behavior, and TF configuration
implicit. The operator must choose the intended algorithm.

## Consequences

### Benefits

- the operator explicitly chooses mapping behavior;
- only one `map -> odom` authority exists;
- one lifecycle and data mount serve both algorithms;
- missing hardware is detected before starting the SLAM container;
- both backends share the same DDS domain and upstream odometry source.

### Costs and risks

- the image is larger because it contains both SLAM implementations;
- changing the selector requires creating or recreating the container;
- host device presence does not prove that ROS topics are publishing;
- backend configuration must remain aligned with driver topic names and the
  robot TF tree;
- backend outputs and persistence mechanisms are not interchangeable;
- RTAB-Map's current `reset_mapping` default deletes its existing database on
  startup.

## Runtime contracts

### SLAM Toolbox

- `/scan` publishes `sensor_msgs/msg/LaserScan` with a frame connected to
  `base_footprint`;
- the TF tree provides `odom -> base_link -> base_footprint` and the fixed
  transform to the laser frame;
- no other process publishes `map -> odom`;
- serialization paths intended to survive recreation are placed under
  `/data`.

### RTAB-Map

- RGB, aligned depth, and camera-info topics match `config/slam.yaml`;
- camera timestamps and calibration are coherent with the aligned images;
- `/odom` publishes `nav_msgs/msg/Odometry` for `base_link`;
- the TF tree connects `base_link` to the optical frames in the image headers;
- database mode is chosen deliberately: `mapping`, `reset_mapping`, or
  `localization`.

## Validation

Validate both positive and negative paths:

1. `--slam_toolbox` accepts a detected `/dev/ttyUSB*` device and rejects or
   skips SLAM when no LiDAR is present.
2. `--slam__rtab` accepts USB ID `8086:0b3a` and rejects or skips SLAM when the
   RealSense is absent.
3. Passing both selectors returns a syntax error without container changes.
4. Each selected Compose model resolves to the expected package, launch file,
   and YAML path.
5. The selected input topics publish at stable rates with compatible QoS.
6. `tf2_echo` can traverse `map -> odom -> base_link` and reach the selected
   sensor frame.
7. Exactly one process publishes `map -> odom`.
8. Mapping updates while the robot moves, and persistence is explicitly tested
   for the selected backend.

## Revisit triggers

Revisit this decision if the combined image becomes too large for deployment,
if different ROS distributions or hardware accelerators are required per
backend, if automatic failover becomes a product requirement, or if Nav2
integration requires a unified persistence and localization contract.
