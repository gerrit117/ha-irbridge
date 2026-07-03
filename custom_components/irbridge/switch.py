"""Switch platform for simple IRBridge on/off devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .bridge import IRBridgeDevice
from .const import (
    CONF_CODEPACK_DEVICE_TYPE,
    CONF_COMMANDS,
    CONF_DEVICE_TYPE,
    CONF_SETUP_MODE,
    DEVICE_TYPE_FAN,
    DOMAIN,
    SETUP_MODE_CODEPACK,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up simple IRBridge switch fallback entities."""
    bridge_device: IRBridgeDevice = hass.data[DOMAIN][entry.entry_id]

    if entry.data.get(CONF_SETUP_MODE) == SETUP_MODE_CODEPACK:
        if entry.data.get(CONF_DEVICE_TYPE) != DEVICE_TYPE_FAN:
            return
        if entry.data.get(CONF_CODEPACK_DEVICE_TYPE) != DEVICE_TYPE_FAN:
            return
        try:
            codepack_data = await hass.async_add_executor_job(
                bridge_device.load_selected_codepack
            )
        except HomeAssistantError:
            _LOGGER.warning(
                "Skipping IRBridge switch with invalid fan codepack",
                extra={"entry_id": entry.entry_id},
                exc_info=True,
            )
            return
        if _has_fan_speeds(codepack_data) or not _has_distinct_on_off(
            codepack_data.get(CONF_COMMANDS)
        ):
            return
        bridge_device._codepack_data = codepack_data
    elif not _has_distinct_on_off(entry.data.get(CONF_COMMANDS)):
        return

    async_add_entities([IRBridgeSwitchEntity(bridge_device)])


class IRBridgeSwitchEntity(RestoreEntity, SwitchEntity):
    """Assumed-state on/off switch for simple IR devices."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(self, bridge_device: IRBridgeDevice) -> None:
        """Initialize the switch."""
        self._bridge_device = bridge_device
        self._attr_unique_id = f"{bridge_device.entry.entry_id}_switch"
        self._attr_device_info = bridge_device.device_info
        self._is_on = False

    async def async_added_to_hass(self) -> None:
        """Restore assumed switch state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._is_on = last_state.state == "on"

    @property
    def is_on(self) -> bool:
        """Return the assumed switch state."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._bridge_device.async_send_command("on")
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._bridge_device.async_send_command("off")
        self._is_on = False
        self.async_write_ha_state()


def _has_distinct_on_off(commands: Any) -> bool:
    """Return whether a command dictionary has separate on and off IR codes."""
    if not isinstance(commands, dict):
        return False
    return isinstance(commands.get("on"), str) and isinstance(commands.get("off"), str)


def _has_fan_speeds(data: dict[str, Any]) -> bool:
    """Return whether a fan codepack has speed commands for FanEntity."""
    commands = data.get(CONF_COMMANDS)
    if not isinstance(commands, dict):
        return False

    metadata_speed = data.get("speed")
    if isinstance(metadata_speed, list):
        for speed in metadata_speed:
            if _fan_speed_code(commands, str(speed)) is not None:
                return True

    ignored = {"off", "on", "power", "toggle", "forward", "reverse"}
    return any(
        isinstance(value, str) and command not in ignored
        for command, value in commands.items()
    )


def _fan_speed_code(commands: dict[str, Any], speed: str) -> str | None:
    """Return a flat or directional fan speed code."""
    value = commands.get(speed)
    if isinstance(value, str) and value.strip():
        return value
    for direction in ("forward", "reverse"):
        directional = commands.get(direction)
        if isinstance(directional, dict):
            value = directional.get(speed)
            if isinstance(value, str) and value.strip():
                return value
    return None
