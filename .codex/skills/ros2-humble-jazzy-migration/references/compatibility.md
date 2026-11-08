# Compatibility references for this repository

The target is ROS 2 Jazzy on Ubuntu Noble 24.04, with system Python 3.12.
Use the installed Jazzy packages to verify APIs, plugin names and runtime defaults.

- ROS binary platforms: https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html
- Official image recipes: https://github.com/osrf/docker_images/tree/master/ros/jazzy/ubuntu/noble
- Jazzy Nav2 migration and optional stamped commands: https://docs.nav2.org/migration/Iron.html
- Jazzy SLAM lifecycle launch: https://github.com/SteveMacenski/slam_toolbox/blob/jazzy/launch/online_async_launch.py

In this integration Nav2 keeps Twist internally. The existing velocity_mux emits
TwistStamped for the STM32 subscriber; teleoperation produces physical
TwistStamped commands. The driver publishes accepted Twist commands to the EKF.
The robot config supplies the mux routing; module defaults remain reusable.

ARM64 availability and a successful AMD64 build are distinct from an ARM64
build or hardware test. Preserve original tuning and serial protocols. Piper
uses its isolated environment; never copy Humble install spaces into Jazzy.
