"""Discovery helpers for local IR transport devices."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import MQTT_TOPIC_TEMPLATE

_LOGGER = logging.getLogger(__name__)

KNOWN_Z2M_IR_MODELS = ("TS1201", "ZS06", "UFO-R11", "UFO R11")
IR_HINTS = ("infrared", "remote", "blaster", "ir_code_to_send", "learned_ir_code")
Z2M_IDENTIFIER_HINTS = ("zigbee2mqtt", "z2m")


@dataclass(frozen=True, slots=True)
class DiscoveredIRBlaster:
    """A registry-backed Zigbee2MQTT IR blaster candidate."""

    device_id: str
    friendly_name: str
    mqtt_topic: str
    name: str
    manufacturer: str | None
    model: str | None

    @property
    def label(self) -> str:
        """Return a readable selector label."""
        details = ", ".join(
            part for part in (self.manufacturer, self.model) if part
        )
        return f"{self.name} ({details})" if details else self.name


def _entry_value(entry: Any, attribute: str) -> Any:
    """Return a registry entry attribute if it exists."""
    return getattr(entry, attribute, None)


def _identifier_parts(identifier: Any) -> tuple[str, ...]:
    """Return safe string parts for a registry identifier."""
    if not identifier:
        return ()
    if isinstance(identifier, (tuple, list, set)):
        return tuple(str(part) for part in identifier if part is not None)
    return (str(identifier),)


def _identifier_domain(identifier: Any) -> str | None:
    """Return the domain-like first part of a registry identifier."""
    parts = _identifier_parts(identifier)
    return parts[0] if parts else None


def _device_name(device: Any) -> str:
    """Return the best available device name."""
    return (
        _entry_value(device, "name_by_user")
        or _entry_value(device, "name")
        or _entry_value(device, "model")
        or _entry_value(device, "id")
        or "Unknown IR blaster"
    )


def _device_registry_name(device: Any) -> str:
    """Return the registry-origin device name, ignoring user overrides."""
    return (
        _entry_value(device, "name")
        or _entry_value(device, "model")
        or _entry_value(device, "id")
        or "Unknown IR blaster"
    )


def _entity_name(entity: Any) -> str:
    """Return searchable text for an entity registry entry."""
    parts = [
        _entry_value(entity, "entity_id"),
        _entry_value(entity, "name"),
        _entry_value(entity, "original_name"),
        _entry_value(entity, "unique_id"),
    ]
    return " ".join(str(part) for part in parts if part)


def _is_mqtt_device(device: Any, entities: list[Any]) -> bool:
    """Return whether a registry device is associated with MQTT."""
    identifiers = _entry_value(device, "identifiers") or set()
    if any(_identifier_domain(identifier) == "mqtt" for identifier in identifiers):
        return True
    return any(_entry_value(entity, "platform") == "mqtt" for entity in entities)


def _has_zigbee2mqtt_hint(device: Any, entities: list[Any]) -> bool:
    """Return whether a registry device looks like a Zigbee2MQTT device."""
    identifiers = _entry_value(device, "identifiers") or set()
    searchable = [
        str(value)
        for identifier in identifiers
        for value in _identifier_parts(identifier)
    ]
    searchable.extend(_entity_name(entity) for entity in entities)
    haystack = " ".join(searchable).lower()
    return any(hint in haystack for hint in Z2M_IDENTIFIER_HINTS)


def _has_ir_hint(device: Any, entities: list[Any]) -> bool:
    """Return whether a registry device appears to be an IR blaster."""
    haystack = " ".join(
        str(part)
        for part in (
            _device_name(device),
            _entry_value(device, "manufacturer"),
            _entry_value(device, "model"),
            *(_entity_name(entity) for entity in entities),
        )
        if part
    ).lower()
    if any(model.lower() in haystack for model in KNOWN_Z2M_IR_MODELS):
        return True
    return any(hint in haystack for hint in IR_HINTS) or bool(
        re.search(r"\bir\b", haystack)
    )


def _has_known_zigbee_ir_model(device: Any) -> bool:
    """Return whether a device model is a known Zigbee2MQTT IR blaster."""
    model = str(_entry_value(device, "model") or "").lower()
    return any(known_model.lower() in model for known_model in KNOWN_Z2M_IR_MODELS)


def _friendly_name_from_device(device: Any) -> str:
    """Infer a Zigbee2MQTT friendly name from a registry device."""
    name = _device_registry_name(device)
    identifiers = _entry_value(device, "identifiers") or set()
    for identifier in identifiers:
        parts = _identifier_parts(identifier)
        if len(parts) < 2 or parts[0] != "mqtt":
            continue
        identifier_text = parts[1]
        if identifier_text.startswith("zigbee2mqtt_"):
            return identifier_text.removeprefix("zigbee2mqtt_")
    return name


def _topic_for_friendly_name(friendly_name: str) -> str:
    """Build the Zigbee2MQTT set topic for a friendly name."""
    clean_name = re.sub(r"\s+", " ", friendly_name.strip())
    return MQTT_TOPIC_TEMPLATE.format(friendly_name=clean_name)


async def async_discover_zigbee2mqtt_ir_blasters(
    hass: HomeAssistant,
) -> list[DiscoveredIRBlaster]:
    """Discover Zigbee2MQTT IR blasters from Home Assistant registries."""
    try:
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
    except Exception:
        _LOGGER.warning(
            "Unable to inspect registries for IR blaster discovery", exc_info=True
        )
        return []
    discovered: list[DiscoveredIRBlaster] = []

    entities_by_device: dict[str, list[Any]] = {}
    for entity in entity_registry.entities.values():
        device_id = _entry_value(entity, "device_id")
        if device_id:
            entities_by_device.setdefault(device_id, []).append(entity)

    for device in device_registry.devices.values():
        try:
            device_id = _entry_value(device, "id")
            if not device_id:
                continue

            entities = entities_by_device.get(device_id, [])
            if not _is_mqtt_device(device, entities):
                continue
            has_zigbee2mqtt_hint = _has_zigbee2mqtt_hint(device, entities)
            has_known_model = _has_known_zigbee_ir_model(device)
            if not has_zigbee2mqtt_hint and not has_known_model:
                continue
            if not _has_ir_hint(device, entities):
                continue

            friendly_name = _friendly_name_from_device(device)
            discovered.append(
                DiscoveredIRBlaster(
                    device_id=device_id,
                    friendly_name=friendly_name,
                    mqtt_topic=_topic_for_friendly_name(friendly_name),
                    name=_device_name(device),
                    manufacturer=_entry_value(device, "manufacturer"),
                    model=_entry_value(device, "model"),
                )
            )
        except Exception:
            _LOGGER.warning(
                "Skipping malformed registry device during IR blaster discovery",
                exc_info=True,
            )

    _LOGGER.debug("Discovered %s Zigbee2MQTT IR blaster candidates", len(discovered))
    return sorted(discovered, key=lambda blaster: blaster.label.lower())
