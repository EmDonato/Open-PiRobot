FROM ros:humble-ros-base-jammy

SHELL ["/bin/bash", "-c"]

ARG USERNAME=openPi
ARG UID=1000
ARG GID=1000


RUN groupadd -g ${GID} ${USERNAME} && \
    useradd -m -u ${UID} -g ${GID} -s /bin/bash ${USERNAME}

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    python3-colcon-common-extensions \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ws

COPY src/ src/

RUN source /opt/ros/humble/setup.bash && \
    colcon build --merge-install \
    --cmake-args -DCMAKE_BUILD_TYPE=Release

COPY docker/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    ROS_DOMAIN_ID=0

USER ${USERNAME} 

RUN echo "source /opt/ros/humble/setup.bash" >> /home/openPi/.bashrc && \
    echo "source /ws/install/setup.bash" >> /home/openPi/.bashrc 

ENTRYPOINT ["/entrypoint.sh"]

CMD ["sleep", "infinity"]