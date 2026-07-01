"""Shared IRBridge runtime objects."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_COMMANDS,
    CONF_DEVICE_TYPE,
    CONF_FRIENDLY_NAME,
    CONF_MQTT_TOPIC,
    CONF_VIRTUAL_NAME,
    DEFAULT_COMMANDS,
    DOMAIN,
    MQTT_PAYLOAD_KEY,
    MQTT_TOPIC_TEMPLATE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class IRBridgeDevice:
    """Virtual IR device backed by a local MQTT IR blaster."""

    hass: HomeAssistant
    entry: ConfigEntry

    @property
    def name(self) -> str:
        """Return the virtual device name."""
        return self.entry.data[CONF_VIRTUAL_NAME]

    @property
    def friendly_name(self) -> str:
        """Return the Zigbee2MQTT friendly name."""
        return self.entry.data[CONF_FRIENDLY_NAME]

    @property
    def device_type(self) -> str:
        """Return the configured future-facing device type."""
        return self.entry.data[CONF_DEVICE_TYPE]

    @property
    def topic(self) -> str:
        """Return the MQTT set topic."""
        configured_topic = self.entry.data.get(CONF_MQTT_TOPIC)
        if configured_topic:
            return configured_topic
        return MQTT_TOPIC_TEMPLATE.format(friendly_name=self.friendly_name)

    @property
    def commands(self) -> dict[str, str]:
        """Return configured command mappings with empty values removed."""
        raw_commands: dict[str, Any] = self.entry.data.get(CONF_COMMANDS, DEFAULT_COMMANDS)
        return {
            str(command): str(code)
            for command, code in raw_commands.items()
            if str(command).strip() and str(code).strip()
        }

    @property
    def device_info(self) -> dict[str, Any]:
        """Return Home Assistant device registry metadata."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "manufacturer": "IRBridge",
            "model": f"Virtual IR {self.device_type}",
            "name": self.name,
            "sw_version": "0.1.0",
        }

    async def async_send_command(self, command: str) -> None:
        """Publish a stored IR command to the configured MQTT topic."""
        normalized_command = command.strip()
        stored_code = self.commands.get(normalized_command)
        if not stored_code:
            raise HomeAssistantError(
                f"Command '{normalized_command}' is not configured for {self.name}"
            )

        payload = json.dumps({MQTT_PAYLOAD_KEY: stored_code})
        _LOGGER.debug(
            "Sending IRBridge command",
            extra={
                "entry_id": self.entry.entry_id,
                "device": self.name,
                "command": normalized_command,
                "topic": self.topic,
            },
        )
        await mqtt.async_publish(self.hass, self.topic, payload, qos=0, retain=False)

    def matches_device(self, device: str) -> bool:
        """Return whether a service device selector matches this virtual device."""
        candidate = device.strip()
        return candidate in {
            self.entry.entry_id,
            self.name,
            self.friendly_name,
            self.entry.title,
        }
