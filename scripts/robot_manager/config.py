from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as error:
    raise RuntimeError(
        "PyYAML is required. Install it with: sudo apt install python3-yaml"
    ) from error


class ConfigError(ValueError):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(
    loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            if key in mapping:
                raise ConfigError(f"Duplicate key: {key}")
        except TypeError as error:
            raise ConfigError("Mapping keys must be scalar values") from error
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


@dataclass(frozen=True)
class HardwareCheck:
    name: str
    type: str
    pattern: str | None = None
    path: str | None = None
    vid: str | None = None
    pid: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class Variant:
    name: str
    aliases: tuple[str, ...] = ()
    environment: dict[str, str] = field(default_factory=dict)
    checks: tuple[str, ...] = ()


@dataclass(frozen=True)
class Module:
    name: str
    compose: Path
    service: str
    container: str
    enabled: bool = True
    default_selected: bool = True
    required: bool = False
    aliases: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()
    default_variant: str | None = None
    variants: dict[str, Variant] = field(default_factory=dict)


@dataclass(frozen=True)
class Registry:
    path: Path
    project_root: Path
    checks: dict[str, HardwareCheck]
    modules: dict[str, Module]
    target_names: dict[str, str]
    variant_aliases: dict[str, tuple[str, str]]

    def default_modules(self) -> list[Module]:
        return [
            module
            for module in self.modules.values()
            if module.enabled and module.default_selected
        ]


ROOT_FIELDS = {"version", "hardware_checks", "modules"}
CHECK_FIELDS = {"type", "pattern", "path", "vid", "pid", "message"}
MODULE_FIELDS = {
    "compose",
    "service",
    "container",
    "enabled",
    "default_selected",
    "required",
    "aliases",
    "checks",
    "default_variant",
    "variants",
}
VARIANT_FIELDS = {"aliases", "environment", "checks"}
RESERVED_ALIASES = {
    "all",
    "build",
    "--build",
    "create",
    "-c",
    "--create",
    "start",
    "-s",
    "--start",
    "stop",
    "-t",
    "--stop",
    "restart",
    "-r",
    "--restart",
    "remove",
    "-x",
    "--remove",
    "status",
    "--status",
    "check",
    "--check",
    "logs",
    "--logs",
    "list",
    "validate-config",
    "help",
    "-h",
    "--help",
    "--config",
    "--variant",
    "--project-root",
}


def _mapping(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{location} must be a mapping")
    for key in value:
        if not isinstance(key, str) or not key:
            raise ConfigError(f"{location} keys must be non-empty strings")
    return value


def _known_fields(data: dict[str, Any], allowed: set[str], location: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise ConfigError(
            f"Unknown field(s) in {location}: {', '.join(sorted(unknown))}"
        )


def _string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{location} must be a non-empty string")
    return value


def _boolean(value: Any, location: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{location} must be a boolean")
    return value


def _strings(value: Any, location: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ConfigError(f"{location} must be a list")
    result = tuple(_string(item, f"{location} item") for item in value)
    if len(result) != len(set(result)):
        raise ConfigError(f"{location} contains duplicate values")
    return result


def _optional_string(value: Any, location: str) -> str | None:
    if value is None:
        return None
    return _string(value, location)


def _parse_check(name: str, raw: Any) -> HardwareCheck:
    location = f"hardware_checks.{name}"
    data = _mapping(raw, location)
    _known_fields(data, CHECK_FIELDS, location)
    check_type = _string(data.get("type"), f"{location}.type")
    message = _optional_string(data.get("message"), f"{location}.message")

    if check_type == "glob":
        required = {"type", "pattern"}
        allowed = required | {"message"}
        pattern = _string(data.get("pattern"), f"{location}.pattern")
        result = HardwareCheck(name, check_type, pattern=pattern, message=message)
    elif check_type == "directory":
        required = {"type", "path"}
        allowed = required | {"message"}
        path = _string(data.get("path"), f"{location}.path")
        result = HardwareCheck(name, check_type, path=path, message=message)
    elif check_type == "usb":
        required = {"type", "vid", "pid"}
        allowed = required | {"message"}
        vid = _string(data.get("vid"), f"{location}.vid").lower()
        pid = _string(data.get("pid"), f"{location}.pid").lower()
        if len(vid) != 4 or len(pid) != 4 or any(
            character not in "0123456789abcdef" for character in vid + pid
        ):
            raise ConfigError(f"{location}.vid and .pid must be four hex digits")
        result = HardwareCheck(name, check_type, vid=vid, pid=pid, message=message)
    else:
        raise ConfigError(f"Unsupported hardware check type in {location}: {check_type}")

    missing = required - set(data)
    extra = set(data) - allowed
    if missing:
        raise ConfigError(f"Missing field(s) in {location}: {', '.join(sorted(missing))}")
    if extra:
        raise ConfigError(
            f"Invalid field(s) for {check_type} check {location}: "
            f"{', '.join(sorted(extra))}"
        )
    return result


def _parse_variant(name: str, raw: Any, location: str) -> Variant:
    data = _mapping(raw, location)
    _known_fields(data, VARIANT_FIELDS, location)
    aliases = _strings(data.get("aliases", []), f"{location}.aliases")
    checks = _strings(data.get("checks", []), f"{location}.checks")
    environment_data = _mapping(data.get("environment", {}), f"{location}.environment")
    environment = {
        _string(key, f"{location}.environment key"): _string(
            value, f"{location}.environment.{key}"
        )
        for key, value in environment_data.items()
    }
    return Variant(name=name, aliases=aliases, environment=environment, checks=checks)


def _parse_module(name: str, raw: Any, project_root: Path) -> Module:
    location = f"modules.{name}"
    data = _mapping(raw, location)
    _known_fields(data, MODULE_FIELDS, location)
    for required_field in ("compose", "service", "container"):
        if required_field not in data:
            raise ConfigError(f"Missing field in {location}: {required_field}")

    compose_value = Path(_string(data["compose"], f"{location}.compose"))
    if compose_value.is_absolute():
        raise ConfigError(f"{location}.compose must be relative to the project root")
    compose = (project_root / compose_value).resolve()
    try:
        compose.relative_to(project_root)
    except ValueError as error:
        raise ConfigError(f"{location}.compose escapes the project root") from error

    variants_data = _mapping(data.get("variants", {}), f"{location}.variants")
    variants = {
        variant_name: _parse_variant(
            variant_name,
            variant_raw,
            f"{location}.variants.{variant_name}",
        )
        for variant_name, variant_raw in variants_data.items()
    }
    default_variant = _optional_string(
        data.get("default_variant"), f"{location}.default_variant"
    )
    if variants and default_variant is None:
        raise ConfigError(f"{location}.default_variant is required when variants exist")
    if not variants and default_variant is not None:
        raise ConfigError(f"{location}.default_variant requires variants")
    if default_variant is not None and default_variant not in variants:
        raise ConfigError(
            f"{location}.default_variant references unknown variant: {default_variant}"
        )

    return Module(
        name=name,
        compose=compose,
        service=_string(data["service"], f"{location}.service"),
        container=_string(data["container"], f"{location}.container"),
        enabled=_boolean(data.get("enabled", True), f"{location}.enabled"),
        default_selected=_boolean(
            data.get("default_selected", True), f"{location}.default_selected"
        ),
        required=_boolean(data.get("required", False), f"{location}.required"),
        aliases=_strings(data.get("aliases", []), f"{location}.aliases"),
        checks=_strings(data.get("checks", []), f"{location}.checks"),
        default_variant=default_variant,
        variants=variants,
    )


def _register_alias(
    aliases: dict[str, Any], alias: str, value: Any, description: str
) -> None:
    if alias in RESERVED_ALIASES or alias.startswith(
        ("--config=", "--variant=", "--project-root=")
    ):
        raise ConfigError(f"Alias '{alias}' in {description} is reserved")
    if alias in aliases:
        raise ConfigError(f"Ambiguous alias '{alias}' in {description}")
    aliases[alias] = value


def load_registry(path: Path, project_root: Path) -> Registry:
    project_root = project_root.resolve()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"Cannot read configuration {path}: {error}") from error
    try:
        raw = yaml.load(text, Loader=UniqueKeyLoader)
    except ConfigError:
        raise
    except yaml.YAMLError as error:
        raise ConfigError(f"Invalid YAML in {path}: {error}") from error

    data = _mapping(raw, "configuration")
    _known_fields(data, ROOT_FIELDS, "configuration")
    if data.get("version") != 1 or isinstance(data.get("version"), bool):
        raise ConfigError("configuration.version must be integer 1")
    checks_data = _mapping(data.get("hardware_checks", {}), "hardware_checks")
    modules_data = _mapping(data.get("modules"), "modules")
    if not modules_data:
        raise ConfigError("modules must contain at least one component")

    checks = {
        name: _parse_check(name, check_raw)
        for name, check_raw in checks_data.items()
    }
    modules = {
        name: _parse_module(name, module_raw, project_root)
        for name, module_raw in modules_data.items()
    }

    target_names: dict[str, str] = {}
    variant_aliases: dict[str, tuple[str, str]] = {}
    all_aliases: dict[str, Any] = {}
    for module in modules.values():
        if module.name in RESERVED_ALIASES:
            raise ConfigError(f"Module name '{module.name}' is reserved")
        _register_alias(all_aliases, module.name, module.name, f"module {module.name}")
        target_names[module.name] = module.name
        for alias in module.aliases:
            _register_alias(all_aliases, alias, module.name, f"module {module.name}")
            target_names[alias] = module.name
        for check_name in module.checks:
            if check_name not in checks:
                raise ConfigError(
                    f"Module {module.name} references unknown check: {check_name}"
                )
        for variant in module.variants.values():
            for check_name in variant.checks:
                if check_name not in checks:
                    raise ConfigError(
                        f"Variant {module.name}={variant.name} references unknown check: "
                        f"{check_name}"
                    )
            for alias in variant.aliases:
                _register_alias(
                    all_aliases,
                    alias,
                    (module.name, variant.name),
                    f"variant {module.name}={variant.name}",
                )
                variant_aliases[alias] = (module.name, variant.name)

    return Registry(
        path=path.resolve(),
        project_root=project_root,
        checks=checks,
        modules=modules,
        target_names=target_names,
        variant_aliases=variant_aliases,
    )


def validate_compose_paths(registry: Registry) -> list[str]:
    errors = []
    for module in registry.modules.values():
        if module.enabled and not module.compose.is_file():
            errors.append(f"{module.name}: Compose file not found: {module.compose}")
    return errors
