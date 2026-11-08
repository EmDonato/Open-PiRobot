from __future__ import annotations

from .compose import ComposeClient, LogFollower
from .config import Module, Registry, Variant
from .hardware import HardwareChecker
from .log import ManagerLogger


class RobotManager:
    HARDWARE_ACTIONS = {"default", "create", "start", "restart"}

    def __init__(
        self,
        registry: Registry,
        logger: ManagerLogger,
        variants: dict[str, str],
        compose: ComposeClient | None = None,
        hardware: HardwareChecker | None = None,
    ):
        self.registry = registry
        self.logger = logger
        self.variants = variants
        self.compose = compose or ComposeClient(logger)
        self.hardware = hardware or HardwareChecker()

    def run(self, action: str, modules: list[Module]) -> int:
        if not self.compose.check_available():
            return 1
        if action == "status":
            print()
            print(f"{'MODULE':<16} {'CONTAINER':<30} STATUS")
            print(f"{'-' * 16:<16} {'-' * 30:<30} {'-' * 12}")
        total = len(modules)
        for index, module in enumerate(modules, start=1):
            self._show_progress(index, total, module.name)
            result = self._run_module(action, module)
            if result != 0 and module.required:
                return 1
        self.logger.message("OK", f"Command '{action}' completed.")
        return 0

    def follow_logs(self, modules: list[Module]) -> int:
        if not self.compose.check_available():
            return 1
        available: list[Module] = []
        for module in modules:
            environment = self._environment(module)
            if self._container_exists(module, environment):
                available.append(module)
                continue
            if self._problem(module, f"Container {module.container} does not exist."):
                return 1
        if not available:
            self.logger.message("WARNING", "There are no container logs to follow.")
            return 0
        self.logger.message("INFO", "Following logs. Press Ctrl+C to stop.")
        return LogFollower(self.logger).follow(available)

    def _run_module(self, action: str, module: Module) -> int:
        environment = self._environment(module)
        if not module.compose.is_file():
            return self._problem(module, f"Compose file not found: {module.compose}")
        if self.compose.compose(module, ["config", "--quiet"], environment) != 0:
            return self._problem(module, "Compose configuration is invalid.")
        if action in self.HARDWARE_ACTIONS or action == "check":
            error = self._check_hardware(module)
            if error:
                return self._problem(module, error)
        if action == "check":
            self._report_hardware_success(module)
            return 0

        handlers = {
            "default": self._default_start,
            "build": self._build,
            "create": self._create,
            "start": self._start,
            "stop": self._stop,
            "restart": self._restart,
            "remove": self._remove,
            "status": self._status,
        }
        result = handlers[action](module, environment)
        if result != 0:
            return self._problem(module, f"The '{action}' command failed.")
        return 0

    def _variant(self, module: Module) -> Variant | None:
        if not module.variants:
            return None
        name = self.variants.get(module.name, module.default_variant)
        return module.variants[name] if name is not None else None

    def _environment(self, module: Module) -> dict[str, str]:
        variant = self._variant(module)
        return dict(variant.environment) if variant else {}

    def _check_hardware(self, module: Module) -> str | None:
        check_names = list(module.checks)
        variant = self._variant(module)
        if variant:
            check_names.extend(variant.checks)
        for check_name in check_names:
            passed, message = self.hardware.check(self.registry.checks[check_name])
            if not passed:
                return message
        return None

    def _problem(self, module: Module, message: str) -> int:
        if module.required:
            self.logger.message("ERROR", f"{module.name} is required: {message}")
            return 1
        self.logger.message("WARNING", f"{module.name} skipped: {message}")
        return 0

    def _container_exists(self, module: Module, environment: dict[str, str]) -> bool:
        return self.compose.inspect(module, environment) == 0

    def _container_running(self, module: Module, environment: dict[str, str]) -> bool:
        result, output = self.compose.inspect_output(
            module, "{{.State.Running}}", environment
        )
        return result == 0 and output == "true"

    def _verify_running(self, module: Module, environment: dict[str, str]) -> int:
        if self._container_running(module, environment):
            self.logger.message("OK", f"{module.container} is running.")
            return 0
        self.logger.message(
            "ERROR", f"{module.container} did not remain running. Check its logs."
        )
        return 1

    def _default_start(self, module: Module, environment: dict[str, str]) -> int:
        if self._container_exists(module, environment):
            self.logger.message(
                "INFO",
                f"Ensuring existing container {module.container} uses the current configuration.",
            )
            if self.compose.compose(
                module, ["up", "--detach", "--no-build", module.service], environment
            ) != 0:
                return 1
            return self._verify_running(module, environment)
        self.logger.message("INFO", f"{module.container} does not exist; building its image.")
        if self.compose.compose(module, ["build", module.service], environment) != 0:
            return 1
        self.logger.message("INFO", f"Creating and starting {module.container}.")
        if self.compose.compose(
            module, ["up", "--detach", "--no-build", module.service], environment
        ) != 0:
            return 1
        return self._verify_running(module, environment)

    def _build(self, module: Module, environment: dict[str, str]) -> int:
        self.logger.message("INFO", f"Building the {module.name} image.")
        return self.compose.compose(module, ["build", module.service], environment)

    def _create(self, module: Module, environment: dict[str, str]) -> int:
        self.logger.message("INFO", f"Building, creating and starting {module.container}.")
        if self.compose.compose(
            module, ["up", "--detach", "--build", module.service], environment
        ) != 0:
            return 1
        return self._verify_running(module, environment)

    def _start(self, module: Module, environment: dict[str, str]) -> int:
        if not self._container_exists(module, environment):
            self.logger.message("ERROR", f"{module.container} does not exist. Use create first.")
            return 1
        self.logger.message("INFO", f"Starting {module.container}.")
        if self.compose.compose(module, ["start", module.service], environment) != 0:
            return 1
        return self._verify_running(module, environment)

    def _stop(self, module: Module, environment: dict[str, str]) -> int:
        if not self._container_exists(module, environment):
            self.logger.message("INFO", f"{module.container} is not created; nothing to stop.")
            return 0
        self.logger.message("INFO", f"Stopping {module.container}.")
        return self.compose.compose(module, ["stop", module.service], environment)

    def _restart(self, module: Module, environment: dict[str, str]) -> int:
        if not self._container_exists(module, environment):
            self.logger.message("ERROR", f"{module.container} does not exist. Use create first.")
            return 1
        self.logger.message("INFO", f"Recreating {module.container} with the current image.")
        if self.compose.compose(
            module,
            ["up", "--detach", "--no-build", "--force-recreate", module.service],
            environment,
        ) != 0:
            return 1
        return self._verify_running(module, environment)

    def _remove(self, module: Module, environment: dict[str, str]) -> int:
        if not self._container_exists(module, environment):
            self.logger.message("INFO", f"{module.container} is not created; nothing to remove.")
            return 0
        self.logger.message("INFO", f"Stopping and removing {module.container}.")
        return self.compose.compose(
            module, ["rm", "--stop", "--force", module.service], environment
        )

    def _status(self, module: Module, environment: dict[str, str]) -> int:
        result, status = self.compose.inspect_output(
            module, "{{.State.Status}}", environment
        )
        if result != 0:
            status = "not-created"
        print(f"{module.name:<16} {module.container:<30} {status}")
        return 0

    def _report_hardware_success(self, module: Module) -> None:
        variant = self._variant(module)
        if variant:
            self.logger.message("OK", f"{module.name} {variant.name} hardware prerequisite found.")
        elif module.checks:
            self.logger.message("OK", f"{module.name} hardware prerequisite found.")
        else:
            self.logger.message("OK", f"{module.name} has no host hardware prerequisite.")

    @staticmethod
    def _show_progress(current: int, total: int, name: str) -> None:
        width = 20
        filled = current * width // total
        percent = current * 100 // total
        print()
        print(
            f"[{'#' * filled}{'-' * (width - filled)}] "
            f"{percent}% ({current}/{total}) {name}"
        )
