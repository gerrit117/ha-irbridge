"""Config flow for IRBridge."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_COMMANDS,
    CONF_DEVICE_TYPE,
    CONF_FRIENDLY_NAME,
    CONF_MQTT_TOPIC,
    CONF_VIRTUAL_NAME,
    DEFAULT_COMMANDS,
    DEVICE_TYPES,
    DOMAIN,
    MQTT_TOPIC_TEMPLATE,
)


class IRBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an IRBridge config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create an IRBridge virtual device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            friendly_name = user_input[CONF_FRIENDLY_NAME].strip()
            mqtt_topic = user_input.get(CONF_MQTT_TOPIC, "").strip()
            virtual_name = user_input[CONF_VIRTUAL_NAME].strip()

            if not friendly_name and not mqtt_topic:
                errors["base"] = "friendly_name_or_topic_required"
            else:
                await self.async_set_unique_id(
                    mqtt_topic or MQTT_TOPIC_TEMPLATE.format(friendly_name=friendly_name)
                )
                self._abort_if_unique_id_configured()

                commands = {
                    command: str(user_input.get(command, "")).strip()
                    for command in DEFAULT_COMMANDS
                }

                return self.async_create_entry(
                    title=virtual_name,
                    data={
                        CONF_VIRTUAL_NAME: virtual_name,
                        CONF_FRIENDLY_NAME: friendly_name,
                        CONF_MQTT_TOPIC: mqtt_topic,
                        CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                        CONF_COMMANDS: commands,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VIRTUAL_NAME): str,
                    vol.Optional(CONF_FRIENDLY_NAME, default=""): str,
                    vol.Optional(CONF_MQTT_TOPIC, default=""): str,
                    vol.Required(CONF_DEVICE_TYPE, default=DEVICE_TYPES[0]): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=DEVICE_TYPES,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional("power", default=""): str,
                    vol.Optional("volume_up", default=""): str,
                    vol.Optional("volume_down", default=""): str,
                    vol.Optional("mute", default=""): str,
                }
            ),
            errors=errors,
        )
