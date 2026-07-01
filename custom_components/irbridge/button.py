"""Button platform for IRBridge."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import IRBridgeDevice
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IRBridge command button entities."""
    bridge_device: IRBridgeDevice = hass.data[DOMAIN][entry.entry_id]
    commands = await bridge_device.async_available_commands()
    async_add_entities(
        IRBridgeCommandButtonEntity(bridge_device, command)
        for command in commands
    )


class IRBridgeCommandButtonEntity(ButtonEntity):
    """Stateless button that sends one configured IR command."""

    _attr_has_entity_name = True

    def __init__(self, bridge_device: IRBridgeDevice, command: str) -> None:
        """Initialize the button."""
        self._bridge_device = bridge_device
        self._command = command
        self._attr_name = command.replace("_", " ").title()
        self._attr_unique_id = f"{bridge_device.entry.entry_id}_{command}_button"
        self._attr_device_info = bridge_device.device_info

    async def async_press(self) -> None:
        """Send this button's configured IR command."""
        await self._bridge_device.async_send_command(self._command)
