"""Bundled SmartIR-compatible codepack discovery and command resolution."""

from __future__ import annotations

import json
import logging
from itertools import permutations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .const import (
    CODEPACK_DEVICE_TYPES,
    CODEPACK_SOURCE_BUNDLED,
    CODEPACK_SOURCE_CUSTOM,
)

_LOGGER = logging.getLogger(__name__)

CODEPACKS_DIR = Path(__file__).parent / "codepacks"
REQUIRED_FIELDS = {"commands"}
UNKNOWN_VALUE = "unknown"

CONTROLLER_TYPE_BROADLINK = "broadlink"
CONTROLLER_TYPE_MQTT = "mqtt"
CONTROLLER_TYPE_XIAOMI = "xiaomi"
CONTROLLER_TYPE_ESPHOME = "esphome"
CONTROLLER_TYPE_LOOKIN = "lookin"
CONTROLLER_TYPE_UNKNOWN = "unknown"

ENCODING_TYPE_BASE64 = "base64"
ENCODING_TYPE_RAW = "raw"
ENCODING_TYPE_PRONTO = "pronto"
ENCODING_TYPE_UNKNOWN = "unknown"

COMPATIBILITY_TYPE_BROADLINK_BASE64 = "broadlink_base64"
COMPATIBILITY_TYPE_MQTT_RAW = "mqtt_raw"
COMPATIBILITY_TYPE_Z2M_BASE64 = "z2m_base64"
COMPATIBILITY_TYPE_ESPHOME_RAW = "esphome_raw"

COMMAND_ALIASES: dict[str, tuple[str, ...]] = {
    "power": ("power", "Power", "toggle", "on", "off"),
    "on": ("on", "power"),
    "off": ("off", "power"),
    "volume_up": ("volumeUp", "volume_up"),
    "volumeup": ("volumeUp", "volume_up"),
    "volumeUp": ("volumeUp", "volume_up"),
    "volume_down": ("volumeDown", "volume_down"),
    "volumedown": ("volumeDown", "volume_down"),
    "volumeDown": ("volumeDown", "volume_down"),
    "mute": ("mute",),
    "play": ("play", "Play", "playPause", "play_pause"),
    "pause": ("pause", "Pause", "playPause", "play_pause"),
    "stop": ("stop", "Stop"),
    "next": ("next", "Next", "nextTrack", "next_track", "nextChannel"),
    "previous": (
        "previous",
        "Previous",
        "previousTrack",
        "previous_track",
        "previousChannel",
    ),
    "channel_up": ("channelUp", "nextChannel"),
    "channel_down": ("channelDown", "previousChannel"),
    "brighten": ("brighten", "brightnessUp", "brightness_up"),
    "dim": ("dim", "brightnessDown", "brightness_down"),
    "warmer": ("warmer", "warm"),
    "colder": ("colder", "cool"),
}

CLIMATE_MODE_ALIASES: dict[str, tuple[str, ...]] = {
    "cool": ("cool",),
    "heat": ("heat",),
    "dry": ("dry",),
    "fan_only": ("fan_only", "fan"),
    "auto": ("auto", "heat_cool"),
}


@dataclass(frozen=True, slots=True)
class CodepackInfo:
    """Metadata for one bundled codepack."""

    device_type: str
    codepack_id: str
    path: str
    source: str
    manufacturer: str
    supported_models: tuple[str, ...]
    commands_encoding: str
    supported_controller: str
    encoding_type: str
    controller_type: str
    compatibility_type: str
    commands: tuple[str, ...]

    @property
    def label(self) -> str:
        """Return a human-readable codepack label."""
        models = ", ".join(self.supported_models) or "Unknown model"
        compatibility = f"{self.supported_controller} {self.commands_encoding}"
        prefix = "Custom: " if self.source == CODEPACK_SOURCE_CUSTOM else ""
        return f"{prefix}{self.manufacturer} {models} ({self.codepack_id}) [{compatibility}]"

    @property
    def ref(self) -> str:
        """Return the stable bundled codepack reference."""
        return f"{self.source}:{self.path}"


@dataclass(frozen=True, slots=True)
class ClimateCodepack:
    """Parsed SmartIR climate codepack metadata."""

    manufacturer: str
    supported_models: tuple[str, ...]
    min_temperature: float
    max_temperature: float
    precision: float
    default_temperature: float | None
    operation_modes: tuple[str, ...]
    fan_modes: tuple[str, ...]
    swing_modes: tuple[str, ...]
    commands: dict[str, Any]
    has_temperature_commands: bool


def is_codepack_path(path: Path) -> bool:
    """Return whether a path can be considered for codepack loading."""
    return (
        path.suffix == ".json"
        and "__MACOSX" not in path.parts
        and not path.name.startswith("._")
    )


def normalize_controller_type(value: Any) -> str:
    """Normalize SmartIR controller metadata to an internal controller type."""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return CONTROLLER_TYPE_UNKNOWN
    if "broadlink" in normalized:
        return CONTROLLER_TYPE_BROADLINK
    if "mqtt" in normalized:
        return CONTROLLER_TYPE_MQTT
    if "esphome" in normalized:
        return CONTROLLER_TYPE_ESPHOME
    if "xiaomi" in normalized or "chuangmi" in normalized:
        return CONTROLLER_TYPE_XIAOMI
    if "look" in normalized:
        return CONTROLLER_TYPE_LOOKIN
    return normalized.replace(" ", "_")


def normalize_encoding_type(value: Any) -> str:
    """Normalize SmartIR command encoding metadata to an internal encoding type."""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ENCODING_TYPE_UNKNOWN
    if "base64" in normalized:
        return ENCODING_TYPE_BASE64
    if "raw" in normalized:
        return ENCODING_TYPE_RAW
    if "pronto" in normalized:
        return ENCODING_TYPE_PRONTO
    return normalized.replace(" ", "_")


def compatibility_type_for(controller_type: str, encoding_type: str) -> str:
    """Return an internal compatibility type for a codepack transport format."""
    if (
        controller_type == CONTROLLER_TYPE_BROADLINK
        and encoding_type == ENCODING_TYPE_BASE64
    ):
        return COMPATIBILITY_TYPE_BROADLINK_BASE64
    if controller_type == CONTROLLER_TYPE_MQTT and encoding_type == ENCODING_TYPE_RAW:
        return COMPATIBILITY_TYPE_MQTT_RAW
    if controller_type == CONTROLLER_TYPE_ESPHOME and encoding_type == ENCODING_TYPE_RAW:
        return COMPATIBILITY_TYPE_ESPHOME_RAW
    if encoding_type == ENCODING_TYPE_BASE64:
        return COMPATIBILITY_TYPE_Z2M_BASE64
    return f"{controller_type}_{encoding_type}"


def validate_codepack_data(
    data: dict[str, Any], path: Path
) -> tuple[list[str], list[str]]:
    """Return validation errors and non-fatal warnings for a SmartIR-style codepack."""
    errors: list[str] = []
    warnings: list[str] = []
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        errors.append(f"missing fields: {', '.join(sorted(missing))}")

    if not isinstance(data.get("manufacturer"), str) or not data.get("manufacturer"):
        warnings.append("manufacturer is missing or invalid; using Unknown")
    if not isinstance(data.get("supportedModels"), list):
        warnings.append("supportedModels is missing or invalid; using codepack id")
    if not isinstance(data.get("commands"), dict):
        errors.append("commands must be an object")
    if not isinstance(data.get("commandsEncoding"), str) or not data.get(
        "commandsEncoding"
    ):
        warnings.append("commandsEncoding is missing or invalid; using unknown")
    if not isinstance(data.get("supportedController"), str) or not data.get(
        "supportedController"
    ):
        warnings.append("supportedController is missing or invalid; using unknown")

    if errors:
        _LOGGER.warning("Skipping invalid codepack %s: %s", path, "; ".join(errors))
    if warnings:
        _LOGGER.warning(
            "Codepack %s has compatibility warnings: %s",
            path,
            "; ".join(warnings),
        )
    return errors, warnings


def _load_json(path: Path) -> dict[str, Any]:
    """Load JSON from a codepack path."""
    with path.open(encoding="utf-8") as codepack_file:
        data = json.load(codepack_file)
    if not isinstance(data, dict):
        raise ValueError("codepack root must be an object")
    return data


def load_codepack_info(
    path: Path,
    root: Path = CODEPACKS_DIR,
    source: str = CODEPACK_SOURCE_BUNDLED,
) -> CodepackInfo | None:
    """Load and validate metadata for one codepack."""
    try:
        device_type = path.relative_to(root).parts[0]
    except (ValueError, IndexError):
        return None

    if device_type not in CODEPACK_DEVICE_TYPES or not is_codepack_path(path):
        return None

    try:
        data = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as err:
        _LOGGER.debug("Unable to load codepack %s: %s", path, err)
        return None

    errors, _warnings = validate_codepack_data(data, path)
    if errors:
        return None

    manufacturer = str(data.get("manufacturer") or "Unknown").strip() or "Unknown"
    supported_models = data.get("supportedModels")
    if isinstance(supported_models, list) and supported_models:
        normalized_models = tuple(str(model) for model in supported_models)
    else:
        normalized_models = (path.stem,)
    commands_encoding = str(data.get("commandsEncoding") or UNKNOWN_VALUE)
    supported_controller = str(data.get("supportedController") or UNKNOWN_VALUE)
    encoding_type = normalize_encoding_type(commands_encoding)
    controller_type = normalize_controller_type(supported_controller)
    commands = tuple(str(command) for command in data["commands"])
    return CodepackInfo(
        device_type=device_type,
        codepack_id=path.stem,
        path=str(path.relative_to(root)),
        source=source,
        manufacturer=manufacturer,
        supported_models=normalized_models,
        commands_encoding=commands_encoding,
        supported_controller=supported_controller,
        encoding_type=encoding_type,
        controller_type=controller_type,
        compatibility_type=compatibility_type_for(controller_type, encoding_type),
        commands=commands,
    )


def discover_codepacks(
    root: Path = CODEPACKS_DIR,
    source: str = CODEPACK_SOURCE_BUNDLED,
) -> list[CodepackInfo]:
    """Discover valid codepacks from one root."""
    if not root.exists():
        return []

    codepacks: list[CodepackInfo] = []
    for path in sorted(root.rglob("*.json")):
        codepack = load_codepack_info(path, root, source)
        if codepack is not None:
            codepacks.append(codepack)
    return codepacks


def discover_all_codepacks(custom_root: Path | None = None) -> list[CodepackInfo]:
    """Discover bundled and optional custom codepacks."""
    bundled = discover_codepacks(CODEPACKS_DIR, CODEPACK_SOURCE_BUNDLED)
    custom = (
        discover_codepacks(custom_root, CODEPACK_SOURCE_CUSTOM)
        if custom_root is not None
        else []
    )
    if not custom:
        return bundled

    by_identity = {
        _codepack_identity(codepack): codepack
        for codepack in bundled
    }
    for codepack in custom:
        by_identity[_codepack_identity(codepack)] = codepack
    return sorted(by_identity.values(), key=lambda codepack: codepack.label.lower())


def _codepack_identity(codepack: CodepackInfo) -> tuple[str, str, tuple[str, ...]]:
    """Return identity used for custom-over-bundled replacement."""
    return (
        codepack.device_type,
        codepack.manufacturer.strip().lower(),
        tuple(model.strip().lower() for model in codepack.supported_models),
    )


def build_codepack_index(
    codepacks: list[CodepackInfo],
) -> dict[str, dict[str, list[CodepackInfo]]]:
    """Build a nested device type/manufacturer index."""
    index: dict[str, dict[str, list[CodepackInfo]]] = {}
    for codepack in codepacks:
        manufacturers = index.setdefault(codepack.device_type, {})
        manufacturers.setdefault(codepack.manufacturer, []).append(codepack)
    for manufacturers in index.values():
        for manufacturer_codepacks in manufacturers.values():
            manufacturer_codepacks.sort(key=lambda codepack: codepack.label.lower())
    return index


def load_codepack(
    device_type: str,
    codepack_id: str,
    *,
    source: str = CODEPACK_SOURCE_BUNDLED,
    codepack_path: str | None = None,
    custom_root: Path | None = None,
) -> dict[str, Any]:
    """Load one bundled or custom codepack."""
    root = custom_root if source == CODEPACK_SOURCE_CUSTOM else CODEPACKS_DIR
    if root is None:
        raise HomeAssistantError("Custom codepack root is not available")
    relative_path = Path(codepack_path or f"{device_type}/{codepack_id}.json")
    path = root / relative_path
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as err:
        raise HomeAssistantError("Codepack path escapes the configured root") from err
    if not is_codepack_path(path) or not path.is_file():
        raise HomeAssistantError(
            f"Codepack '{source}:{device_type}/{codepack_id}' was not found"
        )

    try:
        data = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as err:
        raise HomeAssistantError(
            f"Codepack '{device_type}/{codepack_id}' could not be loaded"
        ) from err

    errors, _warnings = validate_codepack_data(data, path)
    if errors:
        raise HomeAssistantError(
            f"Codepack '{device_type}/{codepack_id}' is invalid: {'; '.join(errors)}"
        )
    controller_type = normalize_controller_type(data.get("supportedController"))
    encoding_type = normalize_encoding_type(data.get("commandsEncoding"))
    data["_irbridge_controller_type"] = controller_type
    data["_irbridge_encoding_type"] = encoding_type
    data["_irbridge_compatibility_type"] = compatibility_type_for(
        controller_type, encoding_type
    )
    return data


def _as_float(value: Any, default: float) -> float:
    """Return a float value or a default."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_string_tuple(value: Any) -> tuple[str, ...]:
    """Return a tuple of strings from a SmartIR metadata list."""
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _has_numeric_leaf(node: Any) -> bool:
    """Return whether a command tree appears to contain temperature keys."""
    if not isinstance(node, dict):
        return False
    for key, value in node.items():
        try:
            float(str(key))
        except ValueError:
            pass
        else:
            if isinstance(value, str):
                return True
        if _has_numeric_leaf(value):
            return True
    return False


def _tree_contains_key(node: Any, expected_key: str) -> bool:
    """Return whether a nested command tree contains a key."""
    if not isinstance(node, dict):
        return False
    for key, value in node.items():
        if str(key) == expected_key:
            return True
        if _tree_contains_key(value, expected_key):
            return True
    return False


def parse_climate_codepack(data: dict[str, Any]) -> ClimateCodepack:
    """Parse SmartIR climate codepack metadata with safe defaults."""
    commands = data.get("commands")
    if not isinstance(commands, dict):
        raise HomeAssistantError("Climate codepack commands must be an object")

    min_temperature = _as_float(data.get("minTemperature"), 16.0)
    max_temperature = _as_float(data.get("maxTemperature"), 30.0)
    precision = _as_float(data.get("precision"), 1.0)
    default_temperature = (
        _as_float(data["defaultTemperature"], min_temperature)
        if "defaultTemperature" in data
        else None
    )
    operation_modes = _as_string_tuple(data.get("operationModes"))
    if not operation_modes:
        operation_modes = tuple(
            command for command, value in commands.items() if isinstance(value, dict)
        )
    fan_modes = _as_string_tuple(data.get("fanModes"))
    swing_modes = _as_string_tuple(data.get("swingModes"))
    supported_models = _as_string_tuple(data.get("supportedModels"))
    if not supported_models:
        supported_models = ("Unknown",)

    return ClimateCodepack(
        manufacturer=str(data.get("manufacturer") or "Unknown"),
        supported_models=supported_models,
        min_temperature=min_temperature,
        max_temperature=max_temperature,
        precision=precision,
        default_temperature=default_temperature,
        operation_modes=operation_modes,
        fan_modes=fan_modes,
        swing_modes=swing_modes,
        commands=commands,
        has_temperature_commands=_has_numeric_leaf(commands),
    )


def _temperature_key_candidates(temperature: float | None) -> tuple[str, ...]:
    """Return SmartIR temperature key candidates."""
    if temperature is None:
        return ()
    candidates: list[str] = []
    numeric_temperature = float(temperature)
    if numeric_temperature.is_integer():
        candidates.append(str(int(numeric_temperature)))
    candidates.append(str(numeric_temperature))
    candidates.append(f"{numeric_temperature:.1f}")
    return tuple(dict.fromkeys(candidates))


def _matching_key(node: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
    """Return the first key in node matching one of the candidates."""
    if not candidates:
        return None
    normalized = {str(key): key for key in node}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def _resolve_path(node: Any, dimensions: tuple[tuple[str, ...], ...]) -> str | None:
    """Resolve nested command data using a dimension candidate path."""
    current = node
    for candidates in dimensions:
        if isinstance(current, str):
            return current
        if not isinstance(current, dict):
            return None
        key = _matching_key(current, candidates)
        if key is None:
            return None
        current = current[key]
    return current if isinstance(current, str) else None


def resolve_climate_command(
    data: dict[str, Any],
    operation_mode: str,
    target_temperature: float | None,
    fan_mode: str | None,
    swing_mode: str | None,
) -> str:
    """Resolve a nested SmartIR climate command."""
    climate = parse_climate_codepack(data)
    commands = climate.commands

    if operation_mode == "off":
        off_command = commands.get("off")
        if isinstance(off_command, str):
            return off_command
        raise HomeAssistantError("Climate codepack does not define an off command")

    operation_candidates = CLIMATE_MODE_ALIASES.get(operation_mode, (operation_mode,))
    operation_key = _matching_key(commands, operation_candidates)
    if operation_key is None:
        raise HomeAssistantError(
            f"Climate codepack does not define operation mode '{operation_mode}'"
        )

    operation_node = commands[operation_key]
    if isinstance(operation_node, str):
        return operation_node

    selected_fan_mode = fan_mode or (climate.fan_modes[0] if climate.fan_modes else None)
    selected_swing_mode = swing_mode or (
        climate.swing_modes[0] if climate.swing_modes else None
    )
    fan_candidates = (selected_fan_mode,) if selected_fan_mode else ()
    swing_candidates = (selected_swing_mode,) if selected_swing_mode else ()
    temperature_candidates = _temperature_key_candidates(target_temperature)

    required_dimensions: list[tuple[str, ...]] = []
    if fan_candidates and _tree_contains_key(operation_node, fan_candidates[0]):
        required_dimensions.append(fan_candidates)
    if swing_candidates and _tree_contains_key(operation_node, swing_candidates[0]):
        required_dimensions.append(swing_candidates)
    if temperature_candidates and _has_numeric_leaf(operation_node):
        required_dimensions.append(temperature_candidates)

    paths = list(permutations(required_dimensions))

    for path in paths:
        resolved = _resolve_path(operation_node, path)
        if resolved is not None:
            return resolved

    _LOGGER.error(
        "Unable to resolve climate command",
        extra={
            "operation_mode": operation_mode,
            "target_temperature": target_temperature,
            "fan_mode": fan_mode,
            "swing_mode": swing_mode,
        },
    )
    raise HomeAssistantError(
        "No matching climate command for "
        f"mode={operation_mode}, temperature={target_temperature}, "
        f"fan={fan_mode}, swing={swing_mode}"
    )


def resolve_codepack_command(
    data: dict[str, Any], command: str, device_type: str
) -> str | None:
    """Resolve a simple IR command from a SmartIR-style codepack."""
    commands = data.get("commands")
    if not isinstance(commands, dict):
        return None

    if device_type == "climate":
        # ClimateEntity uses resolve_climate_command for nested mode/fan/swing/temp.
        return commands.get(command) if isinstance(commands.get(command), str) else None

    candidates = COMMAND_ALIASES.get(command, (command,))
    for candidate in candidates:
        value = commands.get(candidate)
        if isinstance(value, str):
            return value

    return None
