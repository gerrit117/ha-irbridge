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
REQUIRED_FIELDS = {
    "manufacturer",
    "supportedModels",
    "commands",
    "commandsEncoding",
    "supportedController",
}

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
    commands: tuple[str, ...]

    @property
    def label(self) -> str:
        """Return a human-readable codepack label."""
        models = ", ".join(self.supported_models) or "Unknown model"
        return f"{self.codepack_id}: {models}"

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


def validate_codepack_data(data: dict[str, Any], path: Path) -> list[str]:
    """Return validation errors for a SmartIR-style codepack."""
    errors: list[str] = []
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        errors.append(f"missing fields: {', '.join(sorted(missing))}")

    if not isinstance(data.get("manufacturer"), str) or not data.get("manufacturer"):
        errors.append("manufacturer must be a non-empty string")
    if not isinstance(data.get("supportedModels"), list):
        errors.append("supportedModels must be a list")
    if not isinstance(data.get("commands"), dict):
        errors.append("commands must be an object")
    if not isinstance(data.get("commandsEncoding"), str) or not data.get(
        "commandsEncoding"
    ):
        errors.append("commandsEncoding must be a non-empty string")
    if not isinstance(data.get("supportedController"), str) or not data.get(
        "supportedController"
    ):
        errors.append("supportedController must be a non-empty string")

    if errors:
        _LOGGER.debug("Invalid codepack %s: %s", path, "; ".join(errors))
    return errors


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

    if validate_codepack_data(data, path):
        return None

    supported_models = tuple(str(model) for model in data["supportedModels"])
    commands = tuple(str(command) for command in data["commands"])
    return CodepackInfo(
        device_type=device_type,
        codepack_id=path.stem,
        path=str(path.relative_to(root)),
        manufacturer=data["manufacturer"],
        supported_models=supported_models,
        commands_encoding=data["commandsEncoding"],
        supported_controller=data["supportedController"],
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

    errors = validate_codepack_data(data, path)
    if errors:
        raise HomeAssistantError(
            f"Codepack '{device_type}/{codepack_id}' is invalid: {'; '.join(errors)}"
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
