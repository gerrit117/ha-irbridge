"""Bundled SmartIR-compatible codepack discovery and command resolution."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .const import CODEPACK_DEVICE_TYPES

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
    "power": ("power", "on", "off"),
    "on": ("on", "power"),
    "off": ("off", "power"),
    "volume_up": ("volumeUp", "volume_up"),
    "volumeup": ("volumeUp", "volume_up"),
    "volumeUp": ("volumeUp", "volume_up"),
    "volume_down": ("volumeDown", "volume_down"),
    "volumedown": ("volumeDown", "volume_down"),
    "volumeDown": ("volumeDown", "volume_down"),
    "mute": ("mute",),
}


@dataclass(frozen=True, slots=True)
class CodepackInfo:
    """Metadata for one bundled codepack."""

    device_type: str
    codepack_id: str
    path: str
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
        return f"{self.codepack_id}: {models} [{compatibility}]"

    @property
    def ref(self) -> str:
        """Return the stable bundled codepack reference."""
        return f"{self.device_type}/{self.codepack_id}"


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


def load_codepack_info(path: Path, root: Path = CODEPACKS_DIR) -> CodepackInfo | None:
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
        manufacturer=manufacturer,
        supported_models=normalized_models,
        commands_encoding=commands_encoding,
        supported_controller=supported_controller,
        encoding_type=encoding_type,
        controller_type=controller_type,
        compatibility_type=compatibility_type_for(controller_type, encoding_type),
        commands=commands,
    )


def discover_codepacks(root: Path = CODEPACKS_DIR) -> list[CodepackInfo]:
    """Discover bundled valid codepacks."""
    if not root.exists():
        return []

    codepacks: list[CodepackInfo] = []
    for path in sorted(root.rglob("*.json")):
        codepack = load_codepack_info(path, root)
        if codepack is not None:
            codepacks.append(codepack)
    return codepacks


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


def load_codepack(device_type: str, codepack_id: str) -> dict[str, Any]:
    """Load one bundled codepack by type and id."""
    path = CODEPACKS_DIR / device_type / f"{codepack_id}.json"
    if not is_codepack_path(path) or not path.is_file():
        raise HomeAssistantError(f"Codepack '{device_type}/{codepack_id}' was not found")

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


def resolve_codepack_command(
    data: dict[str, Any], command: str, device_type: str
) -> str | None:
    """Resolve a simple IR command from a SmartIR-style codepack."""
    commands = data.get("commands")
    if not isinstance(commands, dict):
        return None

    if device_type == "climate":
        # Climate codepacks are nested by HVAC mode, temperature, fan mode, and swing.
        # TODO: Implement full climate command resolution with ClimateEntity support.
        return commands.get(command) if isinstance(commands.get(command), str) else None

    candidates = COMMAND_ALIASES.get(command, (command,))
    for candidate in candidates:
        value = commands.get(candidate)
        if isinstance(value, str):
            return value

    return None
