"""Light platform for IRBridge SmartIR codepacks."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .bridge import IRBridgeDevice
from .codepacks import resolve_codepack_command
from .const import (
    CONF_CODEPACK_DEVICE_TYPE,
    CONF_DEVICE_TYPE,
    CONF_SETUP_MODE,
    DEVICE_TYPE_LIGHT,
    DOMAIN,
    SETUP_MODE_CODEPACK,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IRBridge light entities."""
    if entry.data.get(CONF_SETUP_MODE) != SETUP_MODE_CODEPACK:
        return
    if entry.data.get(CONF_DEVICE_TYPE) != DEVICE_TYPE_LIGHT:
        return
    if entry.data.get(CONF_CODEPACK_DEVICE_TYPE) != DEVICE_TYPE_LIGHT:
        return

    bridge_device: IRBridgeDevice = hass.data[DOMAIN][entry.entry_id]
    try:
        codepack_data = await hass.async_add_executor_job(
            bridge_device.load_selected_codepack
        )
    except HomeAssistantError:
        _LOGGER.warning(
            "Skipping IRBridge light with invalid codepack",
            extra={"entry_id": entry.entry_id},
            exc_info=True,
        )
        return

    if not _can_create_light(codepack_data):
        _LOGGER.info(
            "Skipping native IRBridge light; no clear on/off commands found",
            extra={"entry_id": entry.entry_id},
        )
        return

    bridge_device._codepack_data = codepack_data
    async_add_entities([IRBridgeLightEntity(bridge_device, codepack_data)])


class IRBridgeLightEntity(RestoreEntity, LightEntity):
    """Assumed-state SmartIR light entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(
        self, bridge_device: IRBridgeDevice, codepack_data: dict[str, Any]
    ) -> None:
        """Initialize the light entity."""
        self._bridge_device = bridge_device
        self._codepack_data = codepack_data
        self._attr_unique_id = f"{bridge_device.entry.entry_id}_light"
        self._attr_device_info = bridge_device.device_info
        self._is_on = False

    async def async_added_to_hass(self) -> None:
        """Restore assumed light state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._is_on = last_state.state == "on"

    @property
    def is_on(self) -> bool:
        """Return the assumed light state."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if _has_command(self._codepack_data, "on"):
            await self._bridge_device.async_send_command("on")
        elif _has_command(self._codepack_data, "power"):
            await self._bridge_device.async_send_command("power")
        else:
            raise HomeAssistantError("Light codepack does not define an on command")
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if _has_command(self._codepack_data, "off"):
            await self._bridge_device.async_send_command("off")
        elif _has_command(self._codepack_data, "power"):
            await self._bridge_device.async_send_command("power")
        else:
            raise HomeAssistantError("Light codepack does not define an off command")
        self._is_on = False
        self.async_write_ha_state()


def _has_command(data: dict[str, Any], command: str) -> bool:
    """Return whether a simple SmartIR command can be resolved."""
    return resolve_codepack_command(data, command, DEVICE_TYPE_LIGHT) is not None


def _can_create_light(data: dict[str, Any]) -> bool:
    """Return whether the codepack can be represented as a native light."""
    return (
        _has_command(data, "on")
        and _has_command(data, "off")
        or _has_command(data, "power")
    )
