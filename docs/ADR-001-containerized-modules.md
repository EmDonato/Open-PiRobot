# ADR-001: Deploy robot capabilities as independent ROS 2 containers

- **Status:** Accepted
- **Date:** 2026-09-28
- **Decision owners:** Open-PiRobot maintainers
- **Scope:** Runtime deployment, module boundaries, ROS 2 communication, and
  container lifecycle

## Context

Open-PiRobot combines components with very different build and runtime needs:

- a custom STM32 serial driver and shared ROS interfaces;
- an LD06 serial LiDAR driver;
- a RealSense stack compiled from pinned upstream sources;
- an EKF, robot description, SLAM, joystick control, and text-to-speech;
- direct access to USB, serial, input, and audio devices;
- deployment primarily on a Raspberry Pi 5, with x86-64 development builds.

A single image would couple all dependency versions and make every change
rebuild the complete robot stack. Running every process directly on the host
would reduce isolation and require ROS 2 Humble and all native dependencies to
be installed and maintained on each robot.

ROS 2 discovery also needs to work between containers and, during development,
with offboard ROS 2 processes. DDS uses dynamic UDP ports and multicast, which
makes a manually maintained Docker port list fragile.

## Decision

Deploy each major capability as an independent Docker Compose service and ROS
2 container:

| Boundary | Service responsibility |
| --- | --- |
| STM32 driver | Serial transport, robot control, IMU, encoder data, joint states |
| LiDAR driver | LD06 serial protocol and laser scans |
| RealSense driver | RGB, depth, alignment, camera calibration, and camera TF |
| Sensor fusion | Differential-drive EKF and `odom -> base_link` |
| SLAM | Exactly one selected mapping backend and `map -> odom` |
| Voice | Piper text-to-speech and host audio |
| Robot bringup | Robot description and fixed transforms |

Use the following integration rules:

1. Every runtime service uses `network_mode: host`.
2. Every service uses Cyclone DDS through
   `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`.
3. Every communicating process uses the same `ROS_DOMAIN_ID`.
4. Hardware drivers receive only the device access required by their existing
   Compose contract. Current serial/USB services use privileged access and
   host device mounts; voice maps `/dev/snd` explicitly.
5. Configuration is kept in the owning module and mounted read-only when the
   service supports runtime configuration.
6. Persistent mapping data is bind-mounted under the SLAM module's `data/`
   directory.
7. `Open-PiRobot.sh` is the central lifecycle interface for the supported
   targets. Each submodule retains a local script and Compose file so it can be
   developed independently.
8. STM32 is treated as mandatory by the central manager; unavailable optional
   modules are skipped with warnings so unrelated capabilities can still run.

## Rationale

Independent images isolate source builds and system dependencies. A RealSense
change does not force a rebuild of the STM32 or EKF image, and a failed
optional module does not have to take down unrelated containers.

Host networking is a deliberate operational tradeoff. It makes DDS discovery
and offboard development straightforward and avoids an incomplete list of
dynamic DDS ports. Cyclone DDS provides one consistent ROS middleware across
all services.

The central manager supplies a uniform operational workflow while keeping
module repositories independently buildable and testable.

## Alternatives considered

### One monolithic robot image

Rejected because it couples unrelated dependencies, increases rebuild time,
enlarges the failure domain, and makes independent module development harder.

### Install ROS 2 and all dependencies directly on the host

Rejected because host state becomes part of the deployment artifact, upgrades
are harder to reproduce, and native dependencies can conflict.

### Docker bridge networks with explicit DDS port mappings

Rejected for the current deployment because DDS discovery, multicast, and
dynamic ports require additional configuration and are harder to debug across
containers and offboard machines.

### A single repository-wide Compose file

Not selected as the only interface. It could simplify dependency ordering, but
would weaken submodule independence. The current manager coordinates the
module-owned Compose files instead.

## Consequences

### Benefits

- failures and rebuilds are isolated by capability;
- modules can pin their own native and ROS dependencies;
- the host does not require a full ROS 2 installation;
- the same images can target ARM64 and, where supported, AMD64;
- developers can run or rebuild one module at a time;
- ROS 2 discovery works without per-topic Docker port maintenance.

### Costs and risks

- host networking removes network isolation between containers;
- identical `ROS_DOMAIN_ID` values can expose the graph to unrelated ROS 2
  processes on the same network;
- privileged containers and broad `/dev` mounts increase security impact;
- startup order does not prove that upstream ROS topics or transforms are
  ready;
- interfaces, topic names, QoS, frames, and clocks become cross-container
  contracts that require integration testing;
- multiple Compose projects require consistent naming and lifecycle tooling.

## Operational constraints

- Use a dedicated ROS domain for each robot or test environment.
- Apply host firewall and network segmentation appropriate to the deployment;
  ROS 2 traffic is not isolated by Docker bridge rules.
- Install and validate host udev rules for persistent device permissions.
- Do not treat device discovery as a health check. Validate message rates,
  timestamps, QoS compatibility, calibration, and TF connectivity.
- Keep a single owner for each dynamic TF edge. In the current design, the EKF
  owns `odom -> base_link` and the selected SLAM backend owns `map -> odom`.
- Prefer narrower device mappings over privileged mode when the driver
  contracts are mature enough to support them.

## Validation

The decision is considered correctly implemented when:

1. every selected Compose file passes `docker compose config --quiet`;
2. all running containers report the same `ROS_DOMAIN_ID` and Cyclone DDS RMW;
3. topics are visible across the selected containers;
4. the TF tree has one publisher per owned dynamic edge;
5. stopping or rebuilding an optional module does not stop unrelated modules;
6. an offboard ROS 2 process on the intended network can discover the required
   graph without manual port forwarding.

## Revisit triggers

Reconsider this decision if security requirements prohibit host networking or
privileged device access, if deterministic orchestration becomes mandatory, or
if deployment expands to enough robots that a dedicated scheduler and managed
DDS discovery provide a clear operational benefit.
