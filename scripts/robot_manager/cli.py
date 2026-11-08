from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .config import ConfigError, Module, Registry, load_registry, validate_compose_paths
from .log import ManagerLogger
from .operations import RobotManager


COMMANDS = {
    "build": "build",
    "--build": "build",
    "create": "create",
    "-c": "create",
    "--create": "create",
    "start": "start",
    "-s": "start",
    "--start": "start",
    "stop": "stop",
    "-t": "stop",
    "--stop": "stop",
    "restart": "restart",
    "-r": "restart",
    "--restart": "restart",
    "remove": "remove",
    "-x": "remove",
    "--remove": "remove",
    "status": "status",
    "--status": "status",
    "check": "check",
    "--check": "check",
    "logs": "logs",
    "--logs": "logs",
    "list": "list",
    "validate-config": "validate-config",
    "help": "help",
    "-h": "help",
    "--help": "help",
}


@dataclass(frozen=True)
class ParsedArguments:
    command: str
    modules: list[Module]
    variants: dict[str, str]


def usage(program: str, registry: Registry | None = None) -> None:
    target_names = ", ".join(registry.modules) if registry else "configured targets"
    print(f"Usage: {program} [--config PATH] [COMMAND] [TARGET ...] [VARIANT]")
    print()
    print("Without arguments: create missing default containers and start them.")
    print()
    print("Commands:")
    print("  build, --build       Build Docker images only")
    print("  create, -c           Build, create and start containers")
    print("  start, -s            Start existing containers")
    print("  stop, -t             Stop containers")
    print("  restart, -r          Recreate containers without building")
    print("  remove, -x           Stop and remove containers")
    print("  status               Show container status")
    print("  check                Check component prerequisites")
    print("  logs                 Follow container logs")
    print("  list                 List registry components")
    print("  validate-config      Validate registry and enabled Compose paths")
    print("  help, -h             Show this help message")
    print()
    print(f"Targets: {target_names}")
    print("Use 'all' for the enabled default group.")
    print("Select a declared variant with --variant module=name.")
    if registry and registry.variant_aliases:
        print("Variant aliases: " + ", ".join(registry.variant_aliases))


def _extract_bootstrap(argv: list[str]) -> tuple[Path | None, list[str]]:
    config: Path | None = None
    remaining: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--project-root":
            if index + 1 >= len(argv):
                raise ConfigError("--project-root requires a path")
            index += 2
            continue
        if argument.startswith("--project-root="):
            index += 1
            continue
        if argument == "--config":
            if index + 1 >= len(argv):
                raise ConfigError("--config requires a path")
            config = Path(argv[index + 1])
            index += 2
            continue
        if argument.startswith("--config="):
            value = argument.partition("=")[2]
            if not value:
                raise ConfigError("--config requires a path")
            config = Path(value)
            index += 1
            continue
        remaining.append(argument)
        index += 1
    return config, remaining


def _project_root(argv: list[str]) -> Path:
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--project-root" and index + 1 < len(argv):
            return Path(argv[index + 1]).resolve()
        if argument.startswith("--project-root="):
            return Path(argument.partition("=")[2]).resolve()
        index += 1
    return Path(__file__).resolve().parents[2]


def _set_variant(
    variants: dict[str, str], registry: Registry, selection: str, source: str
) -> None:
    module_name, separator, variant_name = selection.partition("=")
    if not separator or not module_name or not variant_name:
        raise ConfigError(f"Invalid variant selection '{source}'; use module=name")
    module = registry.modules.get(module_name)
    if module is None:
        raise ConfigError(f"Unknown variant module: {module_name}")
    if not module.enabled:
        raise ConfigError(f"Component '{module_name}' is disabled")
    if variant_name not in module.variants:
        raise ConfigError(f"Unknown variant for {module_name}: {variant_name}")
    previous = variants.get(module_name)
    if previous is not None and previous != variant_name:
        raise ConfigError(
            f"Incompatible variants for {module_name}: {previous} and {variant_name}"
        )
    variants[module_name] = variant_name


def parse_arguments(argv: list[str], registry: Registry) -> ParsedArguments:
    variants: dict[str, str] = {}
    remaining: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--variant":
            if index + 1 >= len(argv):
                raise ConfigError("--variant requires module=name")
            _set_variant(variants, registry, argv[index + 1], argv[index + 1])
            index += 2
            continue
        if argument.startswith("--variant="):
            selection = argument.partition("=")[2]
            _set_variant(variants, registry, selection, argument)
            index += 1
            continue
        if argument in registry.variant_aliases:
            module_name, variant_name = registry.variant_aliases[argument]
            _set_variant(
                variants,
                registry,
                f"{module_name}={variant_name}",
                argument,
            )
            index += 1
            continue
        remaining.append(argument)
        index += 1

    command = "default"
    targets: list[str] = []
    if remaining:
        command_token = remaining[0]
        if command_token not in COMMANDS:
            raise ConfigError(f"Unknown command: {command_token}")
        command = COMMANDS[command_token]
        targets = remaining[1:]

    if command in {"help", "list", "validate-config"}:
        if targets:
            raise ConfigError(f"Command '{command}' does not accept targets")
        return ParsedArguments(command, [], variants)

    selected: list[Module] = []
    selected_names: set[str] = set()
    if not targets:
        targets = ["all"]
    for target in targets:
        if target == "all":
            expanded = registry.default_modules()
        else:
            module_name = registry.target_names.get(target)
            if module_name is None:
                raise ConfigError(f"Unknown container: {target}")
            expanded = [registry.modules[module_name]]
        for module in expanded:
            if not module.enabled:
                raise ConfigError(f"Component '{module.name}' is disabled")
            if module.name not in selected_names:
                selected.append(module)
                selected_names.add(module.name)
    if not selected:
        raise ConfigError("No enabled default components are available")
    return ParsedArguments(command, selected, variants)


def list_modules(registry: Registry) -> None:
    print(f"{'MODULE':<16} {'ENABLED':<9} {'DEFAULT':<9} ALIASES")
    print(f"{'-' * 16:<16} {'-' * 9:<9} {'-' * 9:<9} {'-' * 20}")
    for module in registry.modules.values():
        aliases = ", ".join(module.aliases) if module.aliases else "-"
        print(
            f"{module.name:<16} {str(module.enabled).lower():<9} "
            f"{str(module.default_selected).lower():<9} {aliases}"
        )


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    project_root = _project_root(arguments)
    logger = ManagerLogger(project_root)
    try:
        try:
            config_path, remaining = _extract_bootstrap(arguments)
            if config_path is None:
                config_path = project_root / "config" / "robot.yaml"
            elif not config_path.is_absolute():
                config_path = (Path.cwd() / config_path).resolve()
            registry = load_registry(config_path, project_root)
            parsed = parse_arguments(remaining, registry)
        except (ConfigError, RuntimeError) as error:
            logger.message("ERROR", str(error))
            usage("./Open-PiRobot.sh")
            return 2

        logger.message("INFO", "Open-PiRobot manager started: " + " ".join(remaining))
        if parsed.command == "help":
            usage("./Open-PiRobot.sh", registry)
            return 0
        if parsed.command == "list":
            list_modules(registry)
            return 0
        if parsed.command == "validate-config":
            errors = validate_compose_paths(registry)
            if errors:
                for error in errors:
                    logger.message("ERROR", error)
                return 2
            logger.message(
                "OK",
                f"Configuration is valid: {registry.path} "
                f"({len(registry.modules)} components).",
            )
            return 0

        variant_summary = ", ".join(
            f"{name}={value}" for name, value in parsed.variants.items()
        ) or "defaults"
        logger.message(
            "INFO",
            f"Command: {parsed.command} | Containers: "
            f"{' '.join(module.name for module in parsed.modules)} | "
            f"Variants: {variant_summary}",
        )
        manager = RobotManager(registry, logger, parsed.variants)
        if parsed.command == "logs":
            return manager.follow_logs(parsed.modules)
        return manager.run(parsed.command, parsed.modules)
    except KeyboardInterrupt:
        return 130
    finally:
        logger.close()
