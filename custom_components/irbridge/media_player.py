"""Media player platform for IRBridge SmartIR codepacks."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
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
    DEVICE_TYPE_MEDIA_PLAYER,
    DOMAIN,
    SETUP_MODE_CODEPACK,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IRBridge media player entities."""
    if entry.data.get(CONF_SETUP_MODE) != SETUP_MODE_CODEPACK:
        return
    if entry.data.get(CONF_DEVICE_TYPE) != DEVICE_TYPE_MEDIA_PLAYER:
        return
    if entry.data.get(CONF_CODEPACK_DEVICE_TYPE) != DEVICE_TYPE_MEDIA_PLAYER:
        return

    bridge_device: IRBridgeDevice = hass.data[DOMAIN][entry.entry_id]
    try:
        codepack_data = await hass.async_add_executor_job(
            bridge_device.load_selected_codepack
        )
    except HomeAssistantError:
        _LOGGER.warning(
            "Skipping IRBridge media player with invalid codepack",
            extra={"entry_id": entry.entry_id},
            exc_info=True,
        )
        return

    entity = IRBridgeMediaPlayerEntity(bridge_device, codepack_data)
    if entity.supported_features == MediaPlayerEntityFeature(0):
        _LOGGER.warning(
            "Skipping IRBridge media player because no native commands were found",
            extra={"entry_id": entry.entry_id},
        )
        return

    bridge_device._codepack_data = codepack_data
    async_add_entities([entity])


class IRBridgeMediaPlayerEntity(RestoreEntity, MediaPlayerEntity):
    """Assumed-state SmartIR media player entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(
        self, bridge_device: IRBridgeDevice, codepack_data: dict[str, Any]
    ) -> None:
        """Initialize the media player entity."""
        self._bridge_device = bridge_device
        self._codepack_data = codepack_data
        self._commands = _commands(codepack_data)
        self._attr_unique_id = f"{bridge_device.entry.entry_id}_media_player"
        self._attr_device_info = bridge_device.device_info
        self._attr_supported_features = self._build_supported_features()
        self._state = MediaPlayerState.OFF
        self._source: str | None = None
        self._is_muted = False

    async def async_added_to_hass(self) -> None:
        """Restore assumed media player state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        try:
            self._state = MediaPlayerState(last_state.state)
        except ValueError:
            self._state = MediaPlayerState.OFF
        source = last_state.attributes.get("source")
        if isinstance(source, str) and source in self.source_list:
            self._source = source
        muted = last_state.attributes.get("is_volume_muted")
        if isinstance(muted, bool):
            self._is_muted = muted

    @property
    def state(self) -> MediaPlayerState:
        """Return the current assumed media player state."""
        return self._state

    @property
    def source(self) -> str | None:
        """Return the current assumed source."""
        return self._source

    @property
    def source_list(self) -> list[str]:
        """Return selectable source names."""
        sources = self._commands.get("sources")
        if not isinstance(sources, dict):
            return []
        return [
            str(source)
            for source, value in sources.items()
            if isinstance(value, str) and value.strip()
        ]

    @property
    def is_volume_muted(self) -> bool:
        """Return the current assumed mute state."""
        return self._is_muted

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._async_send_command("on")
        self._state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._async_send_command("off")
        self._state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Send volume up."""
        await self._async_send_command("volume_up")

    async def async_volume_down(self) -> None:
        """Send volume down."""
        await self._async_send_command("volume_down")

    async def async_mute_volume(self, mute: bool) -> None:
        """Toggle mute using the configured IR mute command."""
        await self._async_send_command("mute")
        self._is_muted = mute
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        """Send play."""
        await self._async_send_command("play")
        self._state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        """Send pause."""
        await self._async_send_command("pause")
        self._state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        """Send stop."""
        await self._async_send_command("stop")
        self._state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        """Send next track/channel."""
        await self._async_send_command("next")

    async def async_media_previous_track(self) -> None:
        """Send previous track/channel."""
        await self._async_send_command("previous")

    async def async_select_source(self, source: str) -> None:
        """Send a source selection command."""
        sources = self._commands.get("sources")
        if not isinstance(sources, dict) or source not in sources:
            raise HomeAssistantError(f"Unsupported source: {source}")
        source_code = sources[source]
        if not isinstance(source_code, str) or not source_code.strip():
            raise HomeAssistantError(f"Source '{source}' has no usable IR code")
        await self._bridge_device.async_send_ir_code(source_code)
        self._source = source
        if self._state == MediaPlayerState.OFF:
            self._state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def _async_send_command(self, command: str) -> None:
        """Send a supported media player command."""
        if not _has_command(self._codepack_data, command):
            raise HomeAssistantError(f"Unsupported media player command: {command}")
        await self._bridge_device.async_send_command(command)

    def _build_supported_features(self) -> MediaPlayerEntityFeature:
        """Build supported media player features from SmartIR commands."""
        features = MediaPlayerEntityFeature(0)
        if _has_command(self._codepack_data, "on"):
            features |= MediaPlayerEntityFeature.TURN_ON
        if _has_command(self._codepack_data, "off"):
            features |= MediaPlayerEntityFeature.TURN_OFF
        if _has_command(self._codepack_data, "volume_up") or _has_command(
            self._codepack_data, "volume_down"
        ):
            features |= MediaPlayerEntityFeature.VOLUME_STEP
        if _has_command(self._codepack_data, "mute"):
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if _has_command(self._codepack_data, "play"):
            features |= MediaPlayerEntityFeature.PLAY
        if _has_command(self._codepack_data, "pause"):
            features |= MediaPlayerEntityFeature.PAUSE
        if _has_command(self._codepack_data, "stop"):
            features |= MediaPlayerEntityFeature.STOP
        if _has_command(self._codepack_data, "next"):
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if _has_command(self._codepack_data, "previous"):
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        if self.source_list:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        return features


def _commands(data: dict[str, Any]) -> dict[str, Any]:
    """Return the SmartIR command dictionary."""
    commands = data.get("commands")
    return commands if isinstance(commands, dict) else {}


def _has_command(data: dict[str, Any], command: str) -> bool:
    """Return whether a simple SmartIR command can be resolved."""
    return (
        resolve_codepack_command(data, command, DEVICE_TYPE_MEDIA_PLAYER) is not None
    )
