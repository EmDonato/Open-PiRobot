# Agent instructions

Read and follow [development rules](docs/rule.md) for every task. The existing
code must remain the core: make focused extensions and fixes, and build only
affected components and their necessary dependents. Consult the
[architecture overview](docs/architecture.md) for system context.

## Project context

Open-PiRobot is a modular ROS 2 stack for a Raspberry Pi 5 mobile robot.
The current baseline is Humble; Jazzy is a planned migration target. Check
Dockerfiles and entrypoints for the actual distribution of each component.

Services run in Docker Compose containers with host networking, Cyclone DDS,
and a shared `ROS_DOMAIN_ID`. `Open-PiRobot.sh` manages the central runtime;
ROS 2 does not need to be installed on the host. The deployment target is
ARM64. On x86-64 development machines, use `ROBOT_PLATFORM=linux/amd64` for
components supporting that override.

Repository map:

- `src/`: main bringup and robot description, including Xacro and URDF assets.
- `docker/` and `compose.yaml`: main image, entrypoint, and service.
- `interfaces/`: shared ROS messages and services, in a Git submodule.
- `drivers/`: STM32, LiDAR, and RealSense submodules.
- `modules/`: sensor fusion, SLAM, voice, and teleoperation submodules.
- `README.md`: architecture, startup, configuration, and ROS interfaces.
- `docs/README.md` and `docs/ADR-*.md`: manager reference and architecture decisions.

Read the relevant component README and any applicable local instructions before
changing it. Teleoperation uses its own script or Compose file and is not managed
by the central script.

## Working practices and submodules

- Inspect `git status --short` and existing diffs in the root repository and
  affected submodules before editing. Preserve unrelated and pre-existing work.
- Treat each submodule as a separate repository. Distinguish changes inside a
  submodule from updates to its recorded commit in the parent repository.
  Do not bulk-update or reset submodules as incidental cleanup.
- Keep changes focused on the requested task and follow the component's existing
  conventions. Inspect the implementation when documentation and code disagree.
- Do not manually edit or commit generated build outputs, installations, or logs,
  including `build/`, `install/`, `log/`, and `script_logs/`. Preserve persistent
  maps and databases when cleaning or rebuilding.
- Update relevant documentation when commands, configuration, prerequisites,
  interfaces, or runtime behavior change.

## ROS contracts and runtime constraints

- Check producers and consumers before changing topics, message types, services,
  frame names, QoS, or parameters. Shared interface changes require validation of
  affected dependent components.
- Keep the DDS configuration and `ROS_DOMAIN_ID` consistent across communicating
  services.
- Sensor fusion publishes `/odom` and owns `odom -> base_link`. `/odom/solo` is
  diagnostic encoder odometry and does not publish TF.
- The robot description defines fixed transforms beneath `base_link`. The chosen
  SLAM backend owns `map -> odom`. Avoid competing TF publishers and run only one
  SLAM backend at a time.
- Preserve the manager's hardware checks: STM32 is mandatory, SLAM Toolbox needs
  LiDAR, and RTAB-Map needs RealSense. Image builds do not require attached hardware.
- Distinguish building from running: the manager's `create` command builds and
  starts services. Before RTAB-Map runtime checks, inspect its mapping mode:
  `reset_mapping` deletes the existing database and must not be used on data that
  needs to be preserved.

## Validation

Use component containers for ROS builds and tests; do not assume ROS is installed
on the host. Select checks appropriate to the changed behavior:

- Bash scripts: `bash -n <script>`, including `bash -n Open-PiRobot.sh` for the
  central manager.
- Compose configuration: `docker compose -f <compose-file> config --quiet`, with
  the environment and build contexts required by that component.
- Images: `./Open-PiRobot.sh build <target>` for centrally managed targets. Use
  teleoperation's own Compose file or documented workflow for that module.
- ROS code: build the affected packages and run available tests in the container
  workspace using `colcon test --packages-select <packages>` followed by
  `colcon test-result --verbose`. Include affected consumers when shared
  interfaces change.
- Robot runtime: verify relevant topic rates and data, SLAM input compatibility,
  and the TF chain. Device detection alone does not establish sensor health.

For documentation-only changes, check paths, command accuracy, and the diff;
no image build or hardware test is needed. Use `git diff --check` for tracked
changes and review newly added files as well. Report static checks, builds,
tests, and hardware validation separately, including checks not run and why.
A successful build is not proof of correct operation on the robot.

## Skills and the Humble-to-Jazzy migration

Before migration work, read the relevant skills available in the session and
applicable `SKILL.md` files supplied with the project. Follow their instructions
within the requested task; explicit user instructions take precedence.

Project migration skills:

- [ros2-humble-jazzy-migration](.codex/skills/ros2-humble-jazzy-migration/SKILL.md):
  inventory, migration planning and implementation, package compatibility, and
  recursive submodule management.
- [ros2-jazzy-containers](.codex/skills/ros2-jazzy-containers/SKILL.md):
  Dockerfiles, Compose, entrypoints, dependencies, build isolation, and DDS
  networking for Jazzy containers.
- [ros2-jazzy-validation](.codex/skills/ros2-jazzy-validation/SKILL.md):
  container builds and tests, ROS contracts, runtime diagnostics, and evidence
  reporting for the migration.

Use the main migration skill for overall porting work and the specialized skills
for container changes and validation. Read referenced supporting material when
needed; keep migration procedures in the skills rather than duplicating them
here. If a required skill is missing, report that before performing work that
depends on it.

This file does not initiate the migration. For an assigned migration task,
check base images, dependencies, entrypoints, packages, configuration, and
cross-component contracts together. A textual replacement of `humble` with
`jazzy` is not sufficient validation.
