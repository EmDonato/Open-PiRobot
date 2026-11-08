# Humble to Jazzy migration

Validation date: 2026-10-17. Implemented and functionally verified on the AMD64
development PC for the scope below. Raspberry Pi / physical-robot acceptance
is **NOT RUN**, and the existing package lint suites are not all passing.

## Repository state at validation on 2026-10-17

The root and all seven initialized submodules were already on `jazzy-migration`
when this task started. Partial Dockerfile/Compose migration edits, a `doc/` to
`docs/` move, local agent skills, and three differing submodule checkouts were
already present. Those changes were preserved. No commits, pushes, resets,
submodule updates, image pruning, or changes to the running offboard container
were performed during that validation. At that point the migration was an
**uncommitted working-tree change across separate repositories**.

| Repository | HEAD before and after | Root-recorded gitlink before and after |
| --- | --- | --- |
| Root | `bfeeda22d00b14ce24fb97a65bc836e9c242c4ce` | — |
| `drivers/Ros2_stm32_driver` | `2c11fe86b24e380f81e7913bb08ecabc70752338` | same |
| `drivers/Ros2_lidar_driver` | `3934dd101c410edfe19ef402ee996c6158d2f1e2` | `d731cfce0c64adc6501ecd719d1b7c60fa40b215` |
| `drivers/Ros2_realsense_driver` | `4dbdfb2be2d126af12ff39e1ddd1191f718ba6e7` | same |
| `modules/Ros2_sensor_fusion` | `6eccf535faab551ca51261334a152dc362b83066` | `6a3706bdba2ab206880647da81ba882acf0dbcd5` |
| `modules/Ros2_slam_module` | `7f1444ed7ec45038c0ca4ddcb5c4453816bfa1ad` | `9c73addf01a9eb4a478ab54de8c0d638a70ec4ee` |
| `modules/Ros2_tts_voice` | `1ae6161fa7e8df112349f1ada91334ddfb5eb64d` | same |
| `modules/teleoperation` | `cf5b3ad84a61341d4004d15c011663ffa7fc5a6d` | same |

`interfaces/` is tracked as ordinary source files by the root commit, despite
a stale `.gitmodules` entry and a broken local `interfaces/.git` pointer. Builds
use those root-tracked definitions through the named `interfaces` build
context; their content was not changed. Do not assume `git submodule foreach`
includes this directory or convert its repository layout as migration cleanup.

The three pre-existing checkout differences were retained for validation;
this migration did not silently apply the newer parent-recorded LiDAR, EKF,
or SLAM commits.

## Commit consolidation on 2026-10-21

The seven submodules now have separate migration commits on `jazzy-migration`.
The root records these commits, preserving the working source revisions used
for the AMD64 validation above, including the three pre-existing differences
from the previous root gitlinks. No upstream commits were merged or reset.

| Submodule | Migration commit recorded in the root |
| --- | --- |
| `drivers/Ros2_stm32_driver` | `e947eddc1c304b01575c8831477f0f08bf6c4e7b` |
| `drivers/Ros2_lidar_driver` | `f68d4308191d85bd43458f3b6456f0b74d9b0db8` |
| `drivers/Ros2_realsense_driver` | `fbcbee078e71a1f49b0551641e8b6eb2bbba6f98` |
| `modules/Ros2_sensor_fusion` | `2c571ea23a3d347015606f9a727ed7fa51b598cc` |
| `modules/Ros2_slam_module` | `612e866a11c8fe511361b9033726bd82b1eaa0b9` |
| `modules/Ros2_tts_voice` | `93f72c2df5993bb47dc7c8fe24cedd2472f6de20` |
| `modules/teleoperation` | `ee1f2a90084a5e06d8416b5ea71e8f91237b550d` |

At consolidation, Bash syntax, new/changed Python syntax, Git whitespace, and
all eight Compose models for AMD64 and ARM64 passed static checks. Image builds,
ROS tests, and hardware checks were not repeated; the validation results below
remain dated 2026-10-17, and Raspberry Pi acceptance is still **NOT RUN**.

To obtain this migration in an existing clean checkout on the robot:

```bash
git fetch origin
git switch jazzy-migration
git pull --ff-only --recurse-submodules=on-demand origin jazzy-migration
git submodule sync --recursive
git submodule update --init --recursive
```

Save local changes in each repository before switching. Use the root-recorded
submodule commits, without `--remote`. On the Pi, leave `ROBOT_PLATFORM` unset
and build the Jazzy images locally; this pull transfers source, not Docker images.

## Implementation and dependency inventory

All images use `ros:jazzy-ros-base-noble`, separate `:jazzy` image tags, and
`ROBOT_PLATFORM` (ARM64 by default; AMD64 for this validation). Workspaces are
built inside new image layers under `/ws`, using only the Jazzy underlay.
No host build/install/log directory or Humble binary overlay was reused.
Entrypoints source `/opt/ros/${ROS_DISTRO}/setup.bash` and their built overlay.
Host networking, Cyclone DDS, ROS domain configuration, manager hardware gates,
serial protocol, calibration, EKF algorithm, and TF ownership are preserved.

The existing partial edits already changed the base images, apt package names,
image tags, Noble UID/GID handling, and Piper virtual environment. These were
reviewed and built as part of this task. Additional functional fixes:

- SLAM Toolbox: Jazzy uses a lifecycle node. The existing wrapper now includes
  upstream `online_async_launch.py` with automatic configure/activate, keeping
  its existing `config_file` and `use_sim_time` arguments and tuning.
- Teleoperation: install and resolve configuration through the package share
  directory, with a `config_file` override. Previously `../../config/params.yaml`
  did not exist at runtime, so stamped velocity output was disabled. Align YAML
  keys with the existing launch node names, restoring the configured 0.20 m/s
  limit and joystick settings. Add the launch package's runtime dependencies.
- Add functional smoke checks for those regressions and cross-container EKF/TF.
  Update current documentation, including RealSense's actual launch parameters.

| Context / packages | Compose service | Dependencies / contracts | Risk and check |
| --- | --- | --- | --- |
| Root `src`: `open_pi_bringup`, `robot_descriptor` | `open_pi_robot` | Jazzy Xacro, state publisher; static robot TF | Geometry preserved; late-subscriber TF smoke |
| Root `interfaces/src`: `robot_interfaces` | Built into STM32 and teleoperation | rosidl; `ImuEuler`, `WheelSpeeds`, `ControlCommand` | Regenerated in both images; PTY test imports generated types |
| `drivers/Ros2_stm32_driver`: `stm32_driver` | `stm32_driver` | Jazzy rclcpp/tf2; extra interfaces context; serial, `/cmd_vel` stamped | Native build + simulated serial test |
| `drivers/Ros2_lidar_driver`: `lidar_driver` | `lidar_driver` | Jazzy rclcpp, sensor_msgs; `/scan` SensorDataQoS | Native build + existing lint suite; real serial pending |
| `drivers/Ros2_realsense_driver`: upstream camera/messages/description | `realsense_driver` | SDK `v2.56.5`, wrapper `4.56.4`; RGB-D and camera TF | Source build and no-device load; USB/image validation pending |
| `modules/Ros2_sensor_fusion`: `ekf` | `open-pi-sensor-fusion` | Eigen, rclcpp/tf2; IMU/encoder/accepted Twist -> `/odom`, `odom -> base_link` | Native build + synthetic sensor data across containers |
| `modules/Ros2_slam_module`: two bringup packages | `slam` | Jazzy binary RTAB-Map and Toolbox; RGB-D or scan, odom, TF | Lifecycle/RTAB startup tested; actual maps pending |
| `modules/Ros2_tts_voice`: `piper_tts` | `open-pi-voice-ia` | rclpy, ALSA, Piper 1.7.0 venv; String -> speech | Python 3.12 import/node + PCM generation; speaker pending |
| `modules/teleoperation`: three joy packages | `open-pi-joystick` | joy, teleop_twist_joy, interfaces; stamped raw/final velocity | Synthetic joystick pipeline and loaded parameter assertions |

Each context is its module directory except the root image. ROS communication
does not impose extra image build dependencies. No CI configuration was present.
Piper stays in `/opt/piper`; ROS uses system Python, avoiding PEP 668 overrides.
Piper's transitive wheels and apt versions remain unpinned, as before. No claim
of byte-for-byte reproducibility is made.

Observed versions: Ubuntu 24.04.5, Python 3.12.3, GCC 13.3.0, CMake 3.28.3,
rclcpp 28.1.22, rclpy 7.1.12, Cyclone RMW 2.2.4, SLAM Toolbox 2.8.5,
RTAB-Map ROS 0.23.13, Piper 1.7.0, ONNX Runtime 1.31.0. RealSense wrapper
commit: `bafc21080c5c8e259dadbb309797949aee0dd950`; build and runtime both
report SDK 2.56.5. Python distribution metadata for `piper-tts` must be queried
with `env -u PYTHONPATH /opt/piper/bin/python` to avoid the same-named ROS
package's metadata on the sourced overlay.

Base manifest index observed:
`sha256:103b6c417973394659af6804d4917cd489b91e5ed22eb7bef263025a3bed2410`.
AMD64 manifest:
`sha256:5d90c49a855d75d2a5de6b8836ca49ac2248746b0748d66da79dcaf006225d63`.
ARM64/v8 manifest:
`sha256:d02ae40522e8eb671547efef8ab97c326a62c9efd3a25e48ff3cbe506972edd2`.
These were inspected with `docker buildx imagetools inspect`; ARM64 image
builds and runtime tests were not performed.

## Validation results

| Check | Result | Evidence / limit |
| --- | --- | --- |
| Bash syntax | PASS | Central manager and all module scripts/entrypoints |
| Compose models | PASS | All eight, with both AMD64 and ARM64 overrides |
| Python syntax and Git whitespace | PASS | Source AST parsing; root and submodule `git diff --check` |
| AMD64 image builds | PASS | All eight; manager `build` only, teleoperation's own Compose |
| Declared dependencies | PASS with source-SDK qualification | rosdep checks below |
| STM32 simulated serial | PASS | Existing `tests/smoke_debug_topics.py`; Euler/SI units, diagnostic odom, TF ownership |
| Teleoperation regression | PASS | Installed params, 0.20 limit, full Joy -> stamped command pipeline; no devices/network |
| Robot + EKF across containers | PASS | Synthetic sensors, sustained finite odometry, dynamic odom TF, late static TF subscriber; host network/domain 173 |
| SLAM Toolbox | PASS | Lifecycle reaches active automatically; Ceres plugin loads; clean shutdown |
| RTAB-Map | PASS for startup/shutdown | Expected four RGB-D/odom subscriptions; disposable `/tmp` database in `mapping` mode; no map data |
| RealSense | PASS for library/process load | Pinned wrapper and SDK load; expected no-device warning; launch escalates SIGINT to SIGTERM after 5 s during device search |
| Voice | PASS for software path | rclpy node construction; Piper emits 76,800 bytes of PCM without ALSA playback |
| ARM64 ROS packages | PASS for availability only | All 21 explicitly requested ROS apt packages present in Noble ARM64 package index; no installation/build claimed |
| ARM64 Python wheels | PASS for availability only | Piper and all dependencies downloaded for CPython 3.12/aarch64; not executed |
| Existing package tests | FAIL overall | Lint debt detailed below; no blanket formatting rewrite |
| Pi ARM64 build and robot runtime | NOT RUN | Development PC has no robot sensors/actuators; no sensor rates, mapping quality, audio-device, calibration or physical-motion claims |

Build commands actually used:

```bash
ROBOT_PLATFORM=linux/amd64 ./Open-PiRobot.sh build stm32 lidar fusion robot slam voice realsense
ROBOT_PLATFORM=linux/amd64 docker compose -f modules/teleoperation/compose.yaml build
ROBOT_PLATFORM=linux/amd64 ./Open-PiRobot.sh build slam  # after lifecycle fix
```

For dependency checks, `rosdep update --rosdistro jazzy` ran in a disposable
container and its cache was shared with checks in the built images:
`rosdep check --from-paths /ws/src --ignore-src --rosdistro jazzy`.
All local packages passed. The upstream RealSense full check reports its
source-installed SDK as missing from apt, plus disabled upstream test dependencies
(`launch_pytest`, `python3-tqdm`, `python3-requests`). Its build/exec check passed
with `--dependency-types build --dependency-types exec --skip-keys librealsense2`;
that one explicit exclusion is backed by the source-built SDK and runtime
version check. Upstream RealSense hardware tests remain disabled.

`colcon test --merge-install --packages-select <image-packages>` and
`colcon test-result --verbose` were run as root in disposable image containers.
Initial network-isolated runs could not fetch the XML schema; reruns with
network access resolved that infrastructure failure. Initial full-suite summaries below
include CTest wrapper results as counted by colcon, not unique assertions:

| Package set | Tests | Failures | Skipped | Failure category |
| --- | ---: | ---: | ---: | --- |
| robot_interfaces + stm32_driver | 26 | 2 | 10 | Existing C++ uncrustify |
| lidar_driver | 24 | 0 | 9 | None |
| ekf | 8 | 2 | 1 | Existing C++ uncrustify |
| open_pi_bringup + robot_descriptor | 49 | 41 | 0 | Python/CMake style, unused imports, docstrings, including unused simulation launch |
| robot_interfaces + three joy packages | 19 | 9 | 1 | C++/launch style and docstrings |
| piper_tts | 3 | 1 | 1 | Existing Python flake8 |
| two SLAM bringup packages | 95 | 83 | 0 | Python/CMake style and docstrings |

The SLAM image disables testing in its normal build. Its tests were enabled
in an ephemeral `/tmp/build`, `/tmp/install`, `/tmp/log` workspace using
`colcon build --packages-select rtabmap_bringup slam_toolbox_bringup
--cmake-args -DBUILD_TESTING=ON`, then tested with those same base paths.
Functional smoke checks are separate from these lint suites.

Follow-up validation on 2026-10-17 corrected docstring/import/quote lint issues
in the two launch files already changed by this migration. Both affected
packages now pass their full available test suites: `joy_bringup` **8 tests,
0 failures**, and `slam_toolbox_bringup` **8 tests, 0 failures**. Only the
teleoperation and SLAM images were rebuilt; both functional smoke checks were
repeated successfully. The initial aggregate counts above remain historical
results; unrelated C++ and other Python/CMake lint failures remain unresolved.
Logs: `/tmp/open-pi-jazzy-{teleop,slam}-followup-{build,tests,smoke}.log`.

`docker buildx inspect default` confirms this development PC's current builder
supports only `linux/amd64` and its v2/v3/v4 variants. ARM64 execution is not
configured, so ARM64 image build validation remains blocked pending an ARM64
builder or emulator; package/manifest availability checks are not build evidence.

Logs from this session are `/tmp/open-pi-jazzy-*.log`; they are temporary local
evidence, not committed build products. Manager logs are also in ignored
`script_logs/`. No existing maps or databases were mounted into tests.

## Repeating hardware-free functional checks

From the root, after the AMD64 builds:

```bash
docker run --rm --network none -e ROS_DOMAIN_ID=173 \
  -v "$PWD/drivers/Ros2_stm32_driver/tests:/tests:ro" \
  open-pi-stm32-driver-img:jazzy python3 /tests/smoke_debug_topics.py

docker run --rm --network none -e ROS_DOMAIN_ID=173 \
  -v "$PWD/modules/teleoperation/tests:/tests:ro" \
  open-pi-joystick-img:jazzy python3 /tests/smoke_launch.py

docker run --rm --network none -e ROS_DOMAIN_ID=174 \
  -v "$PWD/modules/Ros2_slam_module/tests:/tests:ro" \
  robot-modules/slam:jazzy python3 /tests/smoke_lifecycle.py
```

For the cross-container graph check, choose an unused ROS domain and test
container names. The following creates no device mounts or motor-control node:

```bash
docker run -d --name jazzy-check-robot --network host -e ROS_DOMAIN_ID=173 \
  open-pi-robot-img:jazzy ros2 launch open_pi_bringup robot_launch.py
docker run -d --name jazzy-check-fusion --network host -e ROS_DOMAIN_ID=173 \
  open-pi-sensor-fusion-img:jazzy
docker run --rm --network host -e ROS_DOMAIN_ID=173 \
  -v "$PWD/tests:/tests:ro" open-pi-stm32-driver-img:jazzy \
  python3 /tests/jazzy_graph_smoke.py
docker stop -t 10 jazzy-check-robot jazzy-check-fusion
docker rm jazzy-check-robot jazzy-check-fusion
```

Always remove the two test containers after a failed assertion as well. This
script publishes simulated IMU and encoder data; do not use an operational
robot's domain. In this session the existing offboard container used domain 0
and was left running unchanged.

## Raspberry Pi acceptance and rollback

On the Pi, unset `ROBOT_PLATFORM` and build the affected Jazzy images natively.
Use the manager's existing hardware checks, then validate one selected SLAM
backend at a time: real scan/image/IMU rates and stamps, command types and QoS,
`map -> odom -> base_link`, camera optical frames, mapping/persistence, serial
watchdog, joystick and ALSA devices. Check RealSense's default Linux UVC backend
against the Pi kernel. No implicit host OS upgrade is required by the container
userland change. Set RTAB-Map to `mapping` before using an existing database;
the repository's preserved `reset_mapping` default deletes it.

Humble commits and local images remain available. For rollback, first save
working-tree changes separately in each repository. Use a separate checkout
of root `bfeeda22d00b14ce24fb97a65bc836e9c242c4ce` and its recorded gitlinks
for the committed Humble baseline; the table above also records the distinct
working submodule SHAs present at task entry. Do not reset this dirty tree.
Existing Humble image tags include `robot-drivers/{stm32,lidar,realsense}-driver:humble-amd64` / `humble-arm64` and `robot-modules/slam:humble`; other pre-existing
images retain their original tags. Restore the matching old Compose files and
configurations together, verify image IDs with `docker image inspect`, and
recreate only the selected services when an operational rollback is intended.
Keep mapping data backed up separately before any database format transition;
rolling software back cannot undo a modified map database.

The project skill's `references/compatibility.md` was absent. Compatibility
was checked against installed packages, builds, and these primary sources:

- [RealSense wrapper 4.56.4 release](https://github.com/realsenseai/realsense-ros/releases/tag/4.56.4)
- [Jazzy SLAM Toolbox lifecycle launch](https://github.com/SteveMacenski/slam_toolbox/blob/jazzy/launch/online_async_launch.py)
- [Official ROS container definitions](https://github.com/osrf/docker_images/tree/master/ros/jazzy/ubuntu/noble)

## Built image IDs (AMD64)

| Tag | Local image ID |
| --- | --- |
| `open-pi-stm32-driver-img:jazzy` | `sha256:e399ba47b98def5290524de552226ca5fc3461035853f79fe8d68214a00430d8` |
| `open-pi-lidar-driver-img:jazzy` | `sha256:11ebc8152daae43be8e465ecf0132cc2487a3f47d8be7b392c8a47c5bcb42431` |
| `open-pi-sensor-fusion-img:jazzy` | `sha256:90de48a262a6da86ea4cbdf5d760a0cf6be065abb2cd21b366d425db23d405c9` |
| `open-pi-robot-img:jazzy` | `sha256:c60ecbcf4757532e1bbaa1d1d5aba7981b78f772f121ac70fd48cddda78e2f10` |
| `open-pi-joystick-img:jazzy` | `sha256:bc3f3a44e351c9d24a603a5f1dc7b209a9da10a2f8761d9731def0c566bfd84e` |
| `robot-modules/slam:jazzy` | `sha256:9fc779862480567fe458a8fb836de3bbd937d16085806e607427fd3086fe53a7` |
| `open-pi-realsense-driver-img:jazzy` | `sha256:b3a97f33eeb490ee90627857aa304ebc3f4bbf9071984c6bd8d1b4ea4a97665a` |
| `open-pi-voice-ia-img:jazzy` | `sha256:d3cf038ef3c3996e8eb25c8c6a8b0ffd267ec16bd7bfc9d1ba2dc4313a6dd4b8` |
