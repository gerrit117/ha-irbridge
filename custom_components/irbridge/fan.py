"""Fan platform for IRBridge SmartIR codepacks."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .bridge import IRBridgeDevice
from .codepacks import resolve_codepack_command
from .const import (
    CONF_CODEPACK_DEVICE_TYPE,
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
    """Set up IRBridge fan entities."""
    if entry.data.get(CONF_SETUP_MODE) != SETUP_MODE_CODEPACK:
        return
    if entry.data.get(CONF_DEVICE_TYPE) != DEVICE_TYPE_FAN:
        return
    if entry.data.get(CONF_CODEPACK_DEVICE_TYPE) != DEVICE_TYPE_FAN:
        return

    bridge_device: IRBridgeDevice = hass.data[DOMAIN][entry.entry_id]
    try:
        codepack_data = await hass.async_add_executor_job(
            bridge_device.load_selected_codepack
        )
    except HomeAssistantError:
        _LOGGER.warning(
            "Skipping IRBridge fan with invalid codepack",
            extra={"entry_id": entry.entry_id},
            exc_info=True,
        )
        return

    speed_names = _speed_names(codepack_data)
    if not speed_names:
        _LOGGER.info(
            "Skipping native IRBridge fan; no speed commands found",
            extra={"entry_id": entry.entry_id},
        )
        return

    bridge_device._codepack_data = codepack_data
    async_add_entities([IRBridgeFanEntity(bridge_device, codepack_data, speed_names)])


class IRBridgeFanEntity(RestoreEntity, FanEntity):
    """Assumed-state SmartIR fan entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(
        self,
        bridge_device: IRBridgeDevice,
        codepack_data: dict[str, Any],
        speed_names: tuple[str, ...],
    ) -> None:
        """Initialize the fan entity."""
        self._bridge_device = bridge_device
        self._codepack_data = codepack_data
        self._speed_names = speed_names
        self._attr_unique_id = f"{bridge_device.entry.entry_id}_fan"
        self._attr_device_info = bridge_device.device_info
        self._attr_speed_count = len(speed_names)
        self._attr_supported_features = FanEntityFeature.SET_SPEED
        if hasattr(FanEntityFeature, "TURN_ON"):
            self._attr_supported_features |= FanEntityFeature.TURN_ON
        if hasattr(FanEntityFeature, "TURN_OFF"):
            self._attr_supported_features |= FanEntityFeature.TURN_OFF
        self._is_on = False
        self._percentage: int | None = None

    async def async_added_to_hass(self) -> None:
        """Restore assumed fan state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        self._is_on = last_state.state == "on"
        percentage = last_state.attributes.get("percentage")
        if isinstance(percentage, int):
            self._percentage = percentage

    @property
    def is_on(self) -> bool:
        """Return the assumed fan power state."""
        return self._is_on

    @property
    def percentage(self) -> int | None:
        """Return the assumed fan speed percentage."""
        return self._percentage

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return

        if _has_command(self._codepack_data, "on"):
            await self._bridge_device.async_send_command("on")
        else:
            speed = _speed_for_percentage(self._speed_names, self._percentage or 100)
            await self._async_send_speed(speed)
            self._percentage = ordered_list_item_to_percentage(self._speed_names, speed)

        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        if _has_command(self._codepack_data, "off"):
            await self._bridge_device.async_send_command("off")
        elif _has_command(self._codepack_data, "power"):
            await self._bridge_device.async_send_command("power")
        else:
            raise HomeAssistantError("Fan codepack does not define an off command")
        self._is_on = False
        self._percentage = 0
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed by percentage."""
        if percentage <= 0:
            await self.async_turn_off()
            return
        speed = _speed_for_percentage(self._speed_names, percentage)
        await self._async_send_speed(speed)
        self._is_on = True
        self._percentage = ordered_list_item_to_percentage(self._speed_names, speed)
        self.async_write_ha_state()

    async def _async_send_speed(self, speed: str) -> None:
        """Send a fan speed command."""
        code = _resolve_speed_code(self._codepack_data, speed)
        if code is None:
            raise HomeAssistantError(f"Fan codepack has no IR code for speed {speed}")
        await self._bridge_device.async_send_ir_code(code)


def _commands(data: dict[str, Any]) -> dict[str, Any]:
    """Return the SmartIR command dictionary."""
    commands = data.get("commands")
    return commands if isinstance(commands, dict) else {}


def _has_command(data: dict[str, Any], command: str) -> bool:
    """Return whether a simple SmartIR command can be resolved."""
    return resolve_codepack_command(data, command, DEVICE_TYPE_FAN) is not None


def _speed_names(data: dict[str, Any]) -> tuple[str, ...]:
    """Return fan speed names that can be mapped to IR commands."""
    commands = _commands(data)
    candidates: list[str] = []
    metadata_speed = data.get("speed")
    if isinstance(metadata_speed, list):
        candidates.extend(str(speed) for speed in metadata_speed)

    ignored = {"off", "on", "power", "toggle", "forward", "reverse"}
    candidates.extend(
        str(command)
        for command, value in commands.items()
        if isinstance(value, str) and str(command) not in ignored
    )
    return tuple(
        dict.fromkeys(
            speed for speed in candidates if _resolve_speed_code(data, speed) is not None
        )
    )


def _resolve_speed_code(data: dict[str, Any], speed: str) -> str | None:
    """Resolve a SmartIR fan speed command from flat or directional structures."""
    commands = _commands(data)
    direct = commands.get(speed)
    if isinstance(direct, str) and direct.strip():
        return direct
    for direction in ("forward", "reverse"):
        directional = commands.get(direction)
        if not isinstance(directional, dict):
            continue
        value = directional.get(speed)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _speed_for_percentage(speed_names: tuple[str, ...], percentage: int) -> str:
    """Return the closest fan speed name for a percentage."""
    return percentage_to_ordered_list_item(speed_names, percentage)
