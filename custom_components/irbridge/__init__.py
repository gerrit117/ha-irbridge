"""IRBridge custom integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .bridge import IRBridgeDevice
from .const import (
    ATTR_COMMAND,
    ATTR_DEVICE,
    DOMAIN,
    PLATFORMS,
    SERVICE_SEND_COMMAND,
)

_LOGGER = logging.getLogger(__name__)

SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE): cv.string,
        vol.Required(ATTR_COMMAND): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up IRBridge services."""
    hass.data.setdefault(DOMAIN, {})

    async def async_handle_send_command(call: ServiceCall) -> None:
        """Handle the irbridge.send_command service."""
        device = call.data[ATTR_DEVICE]
        command = call.data[ATTR_COMMAND]
        for bridge_device in hass.data[DOMAIN].values():
            if bridge_device.matches_device(device):
                await bridge_device.async_send_command(command)
                return

        raise HomeAssistantError(f"IRBridge device '{device}' was not found")

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        async_handle_send_command,
        schema=SEND_COMMAND_SCHEMA,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an IRBridge config entry."""
    await mqtt.async_wait_for_mqtt_client(hass)

    bridge_device = IRBridgeDevice(hass=hass, entry=entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = bridge_device

    _LOGGER.debug("Setting up IRBridge entry %s", entry.entry_id)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an IRBridge config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
