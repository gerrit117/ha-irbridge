"""Remote platform for IRBridge."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import RemoteEntity
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
    """Set up the IRBridge remote entity."""
    bridge_device: IRBridgeDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IRBridgeRemoteEntity(bridge_device)])


class IRBridgeRemoteEntity(RemoteEntity):
    """Virtual IR remote entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, bridge_device: IRBridgeDevice) -> None:
        """Initialize the remote."""
        self._bridge_device = bridge_device
        self._attr_unique_id = f"{bridge_device.entry.entry_id}_remote"
        self._attr_device_info = bridge_device.device_info

    @property
    def is_on(self) -> bool:
        """Return assumed on state for this stateless IR remote."""
        return True

    async def async_send_command(
        self, command: Iterable[str], **kwargs: Any
    ) -> None:
        """Send one or more stored IR commands."""
        for single_command in command:
            await self._bridge_device.async_send_command(single_command)

    async def async_turn_on(
        self, activity: str | None = None, **kwargs: Any
    ) -> None:
        """Send the configured on command."""
        await self._bridge_device.async_send_command("on")

    async def async_turn_off(
        self, activity: str | None = None, **kwargs: Any
    ) -> None:
        """Send the configured off command."""
        await self._bridge_device.async_send_command("off")

    async def async_toggle(
        self, activity: str | None = None, **kwargs: Any
    ) -> None:
        """Toggle using the configured power command."""
        await self._bridge_device.async_send_command("power")

    # TODO: learn_ir_code - add a Home Assistant UI-driven learning flow later.
    # TODO: learned_ir_code - store learned payloads after a backend reports them.
