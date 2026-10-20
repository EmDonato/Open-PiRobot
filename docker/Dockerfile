FROM ros:jazzy-ros-base-noble

SHELL ["/bin/bash", "-c"]

ARG USERNAME=openPi
ARG UID=1000
ARG GID=1000


# Noble reserves UID/GID 1000 for its default ubuntu account.
RUN if id ubuntu >/dev/null 2>&1; then userdel -r ubuntu; fi && \
    groupadd -g ${GID} ${USERNAME} && \
    useradd -m -u ${UID} -g ${GID} -s /bin/bash ${USERNAME}

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    python3-colcon-common-extensions \
    ros-jazzy-rmw-cyclonedds-cpp \
    ros-jazzy-robot-state-publisher \
    ros-jazzy-joint-state-publisher \
    ros-jazzy-tf2-tools \
    ros-jazzy-xacro \
    ros-jazzy-rosbag2-storage-mcap \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ws

COPY src/ src/

RUN source /opt/ros/jazzy/setup.bash && \
    colcon build --merge-install \
    --cmake-args -DCMAKE_BUILD_TYPE=Release

COPY docker/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    ROS_DOMAIN_ID=0

USER ${USERNAME} 

RUN echo "source /opt/ros/jazzy/setup.bash" >> /home/openPi/.bashrc && \
    echo "source /ws/install/setup.bash" >> /home/openPi/.bashrc 

ENTRYPOINT ["/entrypoint.sh"]

CMD ["ros2", "launch", "open_pi_bringup", "robot_launch.py"]