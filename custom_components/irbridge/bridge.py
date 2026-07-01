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
    CONF_CODEPACK_DEVICE_TYPE,
    CONF_CODEPACK_ID,
    CONF_COMMANDS,
    CONF_DEVICE_TYPE,
    CONF_FRIENDLY_NAME,
    CONF_MQTT_TOPIC,
    CONF_SETUP_MODE,
    CONF_VIRTUAL_NAME,
    DEFAULT_COMMANDS,
    DOMAIN,
    MQTT_PAYLOAD_KEY,
    MQTT_TOPIC_TEMPLATE,
    SETUP_MODE_CODEPACK,
)
from .codepacks import (
    COMMAND_ALIASES,
    COMPATIBILITY_TYPE_MQTT_RAW,
    load_codepack,
    resolve_codepack_command,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class IRBridgeDevice:
    """Virtual IR device backed by a local MQTT IR blaster."""

    hass: HomeAssistant
    entry: ConfigEntry
    _codepack_data: dict[str, Any] | None = None

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
    def is_codepack_mode(self) -> bool:
        """Return whether this device uses a bundled codepack."""
        return self.entry.data.get(CONF_SETUP_MODE) == SETUP_MODE_CODEPACK

    @property
    def command_device_type(self) -> str:
        """Return the command source device type."""
        return self.entry.data.get(CONF_CODEPACK_DEVICE_TYPE, self.device_type)

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
    def available_commands(self) -> tuple[str, ...]:
        """Return commands suitable for button entities."""
        if not self.is_codepack_mode:
            return tuple(self.commands)

        codepack_id = self.entry.data.get(CONF_CODEPACK_ID)
        codepack_type = self.entry.data.get(CONF_CODEPACK_DEVICE_TYPE)
        if not codepack_id or not codepack_type:
            return ()

        data = self._codepack_data
        if data is None:
            try:
                data = load_codepack(codepack_type, codepack_id)
            except HomeAssistantError:
                return ()
            self._codepack_data = data

        raw_commands = data.get(CONF_COMMANDS, {})
        if not isinstance(raw_commands, dict):
            return ()

        simple_commands: list[str] = []
        for command, value in raw_commands.items():
            if isinstance(value, str):
                simple_commands.append(str(command))
        return tuple(simple_commands)

    async def async_available_commands(self) -> tuple[str, ...]:
        """Return commands suitable for button entities without blocking the loop."""
        if not self.is_codepack_mode:
            return self.available_commands

        codepack_id = self.entry.data.get(CONF_CODEPACK_ID)
        codepack_type = self.entry.data.get(CONF_CODEPACK_DEVICE_TYPE)
        if not codepack_id or not codepack_type:
            return ()

        if self._codepack_data is None:
            try:
                self._codepack_data = await self.hass.async_add_executor_job(
                    load_codepack, codepack_type, codepack_id
                )
            except HomeAssistantError:
                return ()

        return self.available_commands

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

    async def async_resolve_command(self, command: str) -> str:
        """Resolve a command to an IR code."""
        normalized_command = command.strip()
        if self.is_codepack_mode:
            codepack_id = self.entry.data.get(CONF_CODEPACK_ID)
            codepack_type = self.entry.data.get(CONF_CODEPACK_DEVICE_TYPE)
            if not codepack_id or not codepack_type:
                raise HomeAssistantError(f"No codepack is configured for {self.name}")

            if self._codepack_data is None:
                self._codepack_data = await self.hass.async_add_executor_job(
                    load_codepack, codepack_type, codepack_id
                )

            stored_code = resolve_codepack_command(
                self._codepack_data, normalized_command, codepack_type
            )
            if not stored_code:
                raise HomeAssistantError(
                    f"Command '{normalized_command}' is not available in codepack "
                    f"'{codepack_type}/{codepack_id}' for {self.name}"
                )
            return stored_code

        stored_code = self.commands.get(normalized_command)
        if not stored_code:
            for alias in COMMAND_ALIASES.get(normalized_command, ()):
                stored_code = self.commands.get(alias)
                if stored_code:
                    break

        if not stored_code:
            raise HomeAssistantError(
                f"Command '{normalized_command}' is not configured for {self.name}"
            )
        return stored_code

    async def async_build_payload(self, command: str) -> str:
        """Build the MQTT payload for a command."""
        stored_code = await self.async_resolve_command(command)
        return self.build_payload_for_code(stored_code)

    def build_payload_for_code(self, stored_code: str) -> str:
        """Build the MQTT payload for a stored IR code."""
        if self.is_codepack_mode and self._codepack_data is not None:
            compatibility_type = self._codepack_data.get("_irbridge_compatibility_type")
            if compatibility_type == COMPATIBILITY_TYPE_MQTT_RAW:
                try:
                    parsed_payload = json.loads(stored_code)
                except json.JSONDecodeError:
                    parsed_payload = None
                if isinstance(parsed_payload, dict):
                    return json.dumps(parsed_payload)

        return json.dumps({MQTT_PAYLOAD_KEY: stored_code})

    async def async_send_ir_code(self, stored_code: str) -> None:
        """Publish a resolved IR code to the configured MQTT topic."""
        payload = self.build_payload_for_code(stored_code)
        _LOGGER.debug(
            "Sending resolved IRBridge IR code",
            extra={
                "entry_id": self.entry.entry_id,
                "device": self.name,
                "topic": self.topic,
            },
        )
        await mqtt.async_publish(self.hass, self.topic, payload, qos=0, retain=False)

    async def async_send_command(self, command: str) -> None:
        """Publish a stored IR command to the configured MQTT topic."""
        normalized_command = command.strip()
        payload = await self.async_build_payload(normalized_command)
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
