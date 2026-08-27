#!/usr/bin/env bash

# Central container manager for Open-PiRobot.
# Run without arguments to create missing containers and start the whole robot.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/script_logs"
DEBUG_INFO_LOG="$LOG_DIR/debug_info.txt"
WARNING_ERROR_LOG="$LOG_DIR/warnings_errors.txt"

ALL_TARGETS=(stm32 lidar realsense fusion joystick voice robot)
SELECTED_TARGETS=()
LOG_PIDS=()
HARDWARE_ERROR=""

mkdir -p "$LOG_DIR"
touch "$DEBUG_INFO_LOG"
touch "$WARNING_ERROR_LOG"

# Keep terminal output visible while storing normal and error streams separately.
exec > >(tee -a "$DEBUG_INFO_LOG")
exec 2> >(tee -a "$WARNING_ERROR_LOG" >&2)

usage() {
    echo "Usage: $0 [COMMAND] [CONTAINER ...]"
    echo
    echo "Without arguments: create missing containers and start all containers."
    echo
    echo "Commands:"
    echo "  build,   --build     Build the Docker image only"
    echo "  create,  -c          Build, create and start the container"
    echo "  start,   -s          Start the existing container"
    echo "  stop,    -t          Stop the container"
    echo "  restart, -r          Restart the container"
    echo "  remove,  -x          Stop and remove the container"
    echo "  status               Show the container status"
    echo "  check                Check module prerequisites"
    echo "  logs                 Follow the container logs"
    echo "  help,    -h          Show this help message"
    echo
    echo "Containers:"
    echo "  stm32, lidar, realsense, fusion, joystick, voice, robot"
    echo
    echo "Examples:"
    echo "  $0"
    echo "  $0 build"
    echo "  $0 --build voice lidar"
    echo "  $0 restart stm32 robot"
    echo "  $0 logs stm32"
    echo
    echo "Debug/info log:    $DEBUG_INFO_LOG"
    echo "Warning/error log: $WARNING_ERROR_LOG"
}

log_message() {
    local level="$1"
    local message="$2"

    local line

    line="[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message"

    case "$level" in
        WARNING|ERROR)
            echo "$line" >&2
            ;;
        *)
            echo "$line"
            ;;
    esac
}

compose_file_for() {
    case "$1" in
        robot)     echo "$SCRIPT_DIR/compose.yaml" ;;
        stm32)     echo "$SCRIPT_DIR/drivers/Ros2_stm32_driver/compose.yaml" ;;
        lidar)     echo "$SCRIPT_DIR/drivers/Ros2_lidar_driver/compose.yaml" ;;
        realsense) echo "$SCRIPT_DIR/drivers/Ros2_realsense_driver/compose.yaml" ;;
        fusion)    echo "$SCRIPT_DIR/modules/Ros2_sensor_fusion/compose.yaml" ;;
        joystick)  echo "$SCRIPT_DIR/modules/teleoperation/compose.yaml" ;;
        voice)     echo "$SCRIPT_DIR/modules/Ros2_tts_voice/compose.yaml" ;;
    esac
}

service_for() {
    case "$1" in
        robot)     echo "open_pi_robot" ;;
        stm32)     echo "stm32_driver" ;;
        lidar)     echo "lidar_driver" ;;
        realsense) echo "realsense_driver" ;;
        fusion)    echo "open-pi-sensor-fusion" ;;
        joystick)  echo "open-pi-joystick" ;;
        voice)     echo "open-pi-voice-ia" ;;
    esac
}

container_for() {
    case "$1" in
        robot)     echo "open-pi-robot" ;;
        stm32)     echo "open-pi-stm32-driver" ;;
        lidar)     echo "open-pi-lidar-driver" ;;
        realsense) echo "open-pi-realsense-driver" ;;
        fusion)    echo "open-pi-sensor-fusion" ;;
        joystick)  echo "open-pi-joystick" ;;
        voice)     echo "open-pi-voice-ia" ;;
    esac
}

normalize_target() {
    case "$1" in
        robot|main|bringup|open_pi_robot|open-pi-robot)
            echo "robot"
            ;;
        stm32|stm32_driver|open-pi-stm32-driver)
            echo "stm32"
            ;;
        lidar|lidar_driver|open-pi-lidar-driver)
            echo "lidar"
            ;;
        realsense|camera|realsense_driver|open-pi-realsense-driver)
            echo "realsense"
            ;;
        fusion|sensor-fusion|open-pi-sensor-fusion)
            echo "fusion"
            ;;
        joystick|teleoperation|open-pi-joystick)
            echo "joystick"
            ;;
        voice|tts|voice-ia|open-pi-voice-ia)
            echo "voice"
            ;;
        *)
            return 1
            ;;
    esac
}

target_is_selected() {
    local requested="$1"
    local current

    for current in "${SELECTED_TARGETS[@]}"; do
        if [[ "$current" == "$requested" ]]; then
            return 0
        fi
    done

    return 1
}

select_targets() {
    local argument
    local target

    if [[ $# -eq 0 ]]; then
        SELECTED_TARGETS=("${ALL_TARGETS[@]}")
        return 0
    fi

    for argument in "$@"; do
        if [[ "$argument" == "all" ]]; then
            SELECTED_TARGETS=("${ALL_TARGETS[@]}")
            return 0
        fi

        if ! target="$(normalize_target "$argument")"; then
            log_message "ERROR" "Unknown container: $argument"
            return 1
        fi

        if ! target_is_selected "$target"; then
            SELECTED_TARGETS+=("$target")
        fi
    done
}

compose_for() {
    local target="$1"
    shift

    docker compose --file "$(compose_file_for "$target")" "$@"
}

check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        log_message "ERROR" "Docker is not installed."
        return 1
    fi

    if ! docker compose version >/dev/null 2>&1; then
        log_message "ERROR" "Docker Compose is not available."
        return 1
    fi

    if ! docker info >/dev/null 2>&1; then
        log_message "ERROR" "The Docker daemon is not reachable."
        return 1
    fi

    log_message "OK" "Docker and Docker Compose are available."
}

check_hardware() {
    local target="$1"

    case "$target" in
        stm32)
            if ! compgen -G "/dev/ttyACM*" >/dev/null; then
                HARDWARE_ERROR="No STM32 serial device found in /dev/ttyACM*."
                return 1
            fi
            ;;
        lidar)
            if ! compgen -G "/dev/ttyUSB*" >/dev/null; then
                HARDWARE_ERROR="No LiDAR serial device found in /dev/ttyUSB*."
                return 1
            fi
            ;;
        realsense)
            if ! command -v lsusb >/dev/null 2>&1; then
                HARDWARE_ERROR="The lsusb command is unavailable; RealSense cannot be checked."
                return 1
            fi

            if ! lsusb | grep -qi "8086:0b3a"; then
                HARDWARE_ERROR="RealSense D435i USB device 8086:0b3a was not found."
                return 1
            fi
            ;;
        joystick)
            if ! compgen -G "/dev/input/js*" >/dev/null; then
                HARDWARE_ERROR="No joystick found in /dev/input/js*."
                return 1
            fi
            ;;
        voice)
            if [[ ! -d /dev/snd ]]; then
                HARDWARE_ERROR="No host audio device directory found at /dev/snd."
                return 1
            fi
            ;;
    esac

    HARDWARE_ERROR=""
    return 0
}

report_target_problem() {
    local target="$1"
    local message="$2"

    if [[ "$target" == "stm32" ]]; then
        log_message "ERROR" "STM32 is required: $message"
        return 1
    fi

    log_message "WARNING" "$target skipped: $message"
    return 2
}

prepare_target() {
    local target="$1"
    local needs_hardware="$2"
    local compose_file

    compose_file="$(compose_file_for "$target")"

    if [[ ! -f "$compose_file" ]]; then
        report_target_problem "$target" "Compose file not found: $compose_file"
        return $?
    fi

    if ! compose_for "$target" config --quiet; then
        report_target_problem "$target" "Compose configuration is invalid."
        return $?
    fi

    if [[ "$needs_hardware" == "yes" ]]; then
        if ! check_hardware "$target"; then
            report_target_problem "$target" "$HARDWARE_ERROR"
            return $?
        fi
    fi

    return 0
}

container_exists() {
    docker container inspect "$(container_for "$1")" >/dev/null 2>&1
}

container_is_running() {
    local state

    state="$(docker container inspect --format '{{.State.Running}}' "$(container_for "$1")" 2>/dev/null)"
    [[ "$state" == "true" ]]
}

verify_running() {
    local target="$1"

    if container_is_running "$target"; then
        log_message "OK" "$(container_for "$target") is running."
        return 0
    fi

    log_message "ERROR" "$(container_for "$target") did not remain running. Check its logs."
    return 1
}

show_progress() {
    local current="$1"
    local total="$2"
    local target="$3"
    local width=20
    local filled
    local empty
    local bar=""
    local spaces=""
    local index
    local percent

    filled=$((current * width / total))
    empty=$((width - filled))
    percent=$((current * 100 / total))

    for ((index = 0; index < filled; index++)); do
        bar="${bar}#"
    done

    for ((index = 0; index < empty; index++)); do
        spaces="${spaces}-"
    done

    echo
    echo "[$bar$spaces] $percent% ($current/$total) $target"
}

default_start() {
    local target="$1"
    local service

    service="$(service_for "$target")"

    if container_exists "$target"; then
        log_message "INFO" "Ensuring existing container $(container_for "$target") uses the current configuration."
        compose_for "$target" up --detach --no-build "$service" || return 1
        verify_running "$target"
        return $?
    fi

    log_message "INFO" "$(container_for "$target") does not exist; building its image."
    compose_for "$target" build "$service" || return 1

    log_message "INFO" "Creating and starting $(container_for "$target")."
    compose_for "$target" up --detach --no-build "$service" || return 1
    verify_running "$target"
}

build_target() {
    log_message "INFO" "Building the $1 image."
    compose_for "$1" build "$(service_for "$1")"
}

create_target() {
    log_message "INFO" "Building, creating and starting $(container_for "$1")."
    compose_for "$1" up --detach --build "$(service_for "$1")" || return 1
    verify_running "$1"
}

start_target() {
    if ! container_exists "$1"; then
        log_message "ERROR" "$(container_for "$1") does not exist. Use create first."
        return 1
    fi

    log_message "INFO" "Starting $(container_for "$1")."
    compose_for "$1" start "$(service_for "$1")" || return 1
    verify_running "$1"
}

stop_target() {
    if ! container_exists "$1"; then
        log_message "INFO" "$(container_for "$1") is not created; nothing to stop."
        return 0
    fi

    log_message "INFO" "Stopping $(container_for "$1")."
    compose_for "$1" stop "$(service_for "$1")"
}

restart_target() {
    if ! container_exists "$1"; then
        log_message "ERROR" "$(container_for "$1") does not exist. Use create first."
        return 1
    fi

    log_message "INFO" "Restarting $(container_for "$1")."
    compose_for "$1" restart "$(service_for "$1")" || return 1
    verify_running "$1"
}

remove_target() {
    if ! container_exists "$1"; then
        log_message "INFO" "$(container_for "$1") is not created; nothing to remove."
        return 0
    fi

    log_message "INFO" "Stopping and removing $(container_for "$1")."
    compose_for "$1" rm --stop --force "$(service_for "$1")"
}

status_target() {
    local container
    local status

    container="$(container_for "$1")"

    if container_exists "$1"; then
        status="$(docker container inspect --format '{{.State.Status}}' "$container")"
    else
        status="not-created"
    fi

    printf "%-12s %-30s %s\n" "$1" "$container" "$status"
}

check_target() {
    local target="$1"

    if ! check_hardware "$target"; then
        report_target_problem "$target" "$HARDWARE_ERROR"
        return $?
    fi

    case "$target" in
        robot|fusion)
            log_message "OK" "$target has no host hardware prerequisite."
            ;;
        *)
            log_message "OK" "$target hardware prerequisite found."
            ;;
    esac
}

run_action_for_target() {
    local action="$1"
    local target="$2"
    local needs_hardware="no"
    local prepare_result
    local action_result

    case "$action" in
        default|create|start|restart)
            needs_hardware="yes"
            ;;
    esac

    prepare_target "$target" "$needs_hardware"
    prepare_result=$?

    if [[ $prepare_result -eq 1 ]]; then
        return 1
    fi

    if [[ $prepare_result -eq 2 ]]; then
        return 0
    fi

    case "$action" in
        default) default_start "$target" ;;
        build)   build_target "$target" ;;
        create)  create_target "$target" ;;
        start)   start_target "$target" ;;
        stop)    stop_target "$target" ;;
        restart) restart_target "$target" ;;
        remove)  remove_target "$target" ;;
        status)  status_target "$target" ;;
        check)   check_target "$target" ;;
    esac

    action_result=$?

    if [[ $action_result -ne 0 ]]; then
        report_target_problem "$target" "The '$action' command failed."
        action_result=$?

        if [[ $action_result -eq 1 ]]; then
            return 1
        fi
    fi

    return 0
}

run_action() {
    local action="$1"
    local total="${#SELECTED_TARGETS[@]}"
    local current=0
    local target

    if ! check_docker; then
        return 1
    fi

    if [[ "$action" == "status" ]]; then
        echo
        printf "%-12s %-30s %s\n" "MODULE" "CONTAINER" "STATUS"
        printf "%-12s %-30s %s\n" "------------" "------------------------------" "------------"
    fi

    for target in "${SELECTED_TARGETS[@]}"; do
        current=$((current + 1))
        show_progress "$current" "$total" "$target"

        if ! run_action_for_target "$action" "$target"; then
            return 1
        fi
    done

    log_message "OK" "Command '$action' completed."
}

stop_log_followers() {
    local pid

    echo
    log_message "INFO" "Stopping log follow."

    for pid in "${LOG_PIDS[@]}"; do
        kill "$pid" >/dev/null 2>&1 || true
    done
}

follow_logs() {
    local target
    local container
    local available_targets=()
    local result

    if ! check_docker; then
        return 1
    fi

    # Check every target before opening streams, so STM32 can fail cleanly.
    for target in "${SELECTED_TARGETS[@]}"; do
        if container_exists "$target"; then
            available_targets+=("$target")
            continue
        fi

        report_target_problem "$target" "Container $(container_for "$target") does not exist."
        result=$?

        if [[ $result -eq 1 ]]; then
            return 1
        fi
    done

    if [[ ${#available_targets[@]} -eq 0 ]]; then
        log_message "WARNING" "There are no container logs to follow."
        return 0
    fi

    log_message "INFO" "Following logs. Press Ctrl+C to stop."
    trap stop_log_followers INT TERM

    for target in "${available_targets[@]}"; do
        container="$(container_for "$target")"
        docker logs --follow --tail 50 "$container" 2>&1 | sed -u "s/^/[$target] /" &
        LOG_PIDS+=("$!")
    done

    wait
}

main() {
    local command="default"

    log_message "INFO" "Open-PiRobot manager started: $*"

    if [[ $# -gt 0 ]]; then
        command="$1"
        shift
    fi

    case "$command" in
        build|--build)
            command="build"
            ;;
        create|-c|--create)
            command="create"
            ;;
        start|-s|--start)
            command="start"
            ;;
        stop|-t|--stop)
            command="stop"
            ;;
        restart|-r|--restart)
            command="restart"
            ;;
        remove|-x|--remove)
            command="remove"
            ;;
        status|--status)
            command="status"
            ;;
        check|--check)
            command="check"
            ;;
        logs|--logs)
            command="logs"
            ;;
        default)
            ;;
        help|-h|--help)
            usage
            return 0
            ;;
        *)
            log_message "ERROR" "Unknown command: $command"
            usage
            return 2
            ;;
    esac

    if ! select_targets "$@"; then
        usage
        return 2
    fi

    log_message "INFO" "Command: $command | Containers: ${SELECTED_TARGETS[*]}"

    if [[ "$command" == "logs" ]]; then
        follow_logs
        return $?
    fi

    run_action "$command"
}

main "$@"
