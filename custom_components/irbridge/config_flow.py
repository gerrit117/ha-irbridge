"""Config flow for IRBridge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .codepacks import CodepackInfo, build_codepack_index, discover_all_codepacks
from .const import (
    CODEPACK_DEVICE_TYPES,
    CONF_CODEPACK_DEVICE_TYPE,
    CONF_CODEPACK_ID,
    CONF_CODEPACK_MANUFACTURER,
    CONF_CODEPACK_PATH,
    CONF_CODEPACK_SOURCE,
    CONF_COMMANDS,
    CONF_DEVICE_TYPE,
    CONF_FRIENDLY_NAME,
    CONF_IR_BLASTER_DEVICE_ID,
    CONF_IR_BLASTER_SELECTOR,
    CONF_MQTT_TOPIC,
    CONF_SETUP_MODE,
    CONF_VIRTUAL_NAME,
    DEFAULT_COMMANDS,
    DEVICE_TYPES,
    DOMAIN,
    CUSTOM_CODEPACK_DIR,
    MANUAL_IR_BLASTER_SELECTOR,
    MQTT_TOPIC_TEMPLATE,
    SETUP_MODE_CODEPACK,
    SETUP_MODE_MANUAL,
    SETUP_MODES,
)
from .discovery import DiscoveredIRBlaster, async_discover_zigbee2mqtt_ir_blasters


class IRBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an IRBridge config flow."""

    VERSION = 1
    _common_data: dict[str, Any]
    _codepack_device_type: str
    _codepack_manufacturer: str
    _codepack_index: dict[str, dict[str, list[CodepackInfo]]] | None = None
    _discovered_blasters: dict[str, DiscoveredIRBlaster] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Collect common IRBridge virtual device settings."""
        errors: dict[str, str] = {}
        discovered_blasters = await self._async_get_discovered_blasters()

        if user_input is not None:
            virtual_name = user_input[CONF_VIRTUAL_NAME].strip()
            selected_blaster = user_input[CONF_IR_BLASTER_SELECTOR]

            if selected_blaster == MANUAL_IR_BLASTER_SELECTOR:
                self._common_data = {
                    CONF_VIRTUAL_NAME: virtual_name,
                    CONF_SETUP_MODE: user_input[CONF_SETUP_MODE],
                }
                return await self.async_step_manual_transport()

            blaster = discovered_blasters.get(selected_blaster)
            if blaster is None:
                errors["base"] = "ir_blaster_not_found"
            else:
                topic = blaster.mqtt_topic
                await self.async_set_unique_id(f"{topic}:{virtual_name}")
                self._abort_if_unique_id_configured()

                self._common_data = {
                    CONF_VIRTUAL_NAME: virtual_name,
                    CONF_FRIENDLY_NAME: blaster.friendly_name,
                    CONF_MQTT_TOPIC: topic,
                    CONF_IR_BLASTER_DEVICE_ID: blaster.device_id,
                    CONF_SETUP_MODE: user_input[CONF_SETUP_MODE],
                }

                if user_input[CONF_SETUP_MODE] == SETUP_MODE_CODEPACK:
                    return await self.async_step_codepack_type()
                return await self.async_step_manual()

        blaster_options = [
            {"value": blaster.device_id, "label": blaster.label}
            for blaster in discovered_blasters.values()
        ]
        blaster_options.append(
            {"value": MANUAL_IR_BLASTER_SELECTOR, "label": "Manual MQTT topic"}
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VIRTUAL_NAME): str,
                    vol.Required(CONF_IR_BLASTER_SELECTOR): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=blaster_options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_SETUP_MODE, default=SETUP_MODE_MANUAL): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=SETUP_MODES,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_manual_transport(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Collect manual MQTT transport settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            friendly_name = user_input.get(CONF_FRIENDLY_NAME, "").strip()
            mqtt_topic = user_input.get(CONF_MQTT_TOPIC, "").strip()

            if not friendly_name and not mqtt_topic:
                errors["base"] = "friendly_name_or_topic_required"
            else:
                topic = mqtt_topic or MQTT_TOPIC_TEMPLATE.format(
                    friendly_name=friendly_name
                )
                await self.async_set_unique_id(
                    f"{topic}:{self._common_data[CONF_VIRTUAL_NAME]}"
                )
                self._abort_if_unique_id_configured()
                self._common_data.update(
                    {
                        CONF_FRIENDLY_NAME: friendly_name,
                        CONF_MQTT_TOPIC: topic,
                    }
                )
                if self._common_data[CONF_SETUP_MODE] == SETUP_MODE_CODEPACK:
                    return await self.async_step_codepack_type()
                return await self.async_step_manual()

        return self.async_show_form(
            step_id="manual_transport",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_FRIENDLY_NAME, default=""): str,
                    vol.Optional(CONF_MQTT_TOPIC, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Collect manual command mappings."""
        if user_input is not None:
            commands = {
                command: str(user_input.get(command, "")).strip()
                for command in DEFAULT_COMMANDS
            }

            data = {
                **self._common_data,
                CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                CONF_COMMANDS: commands,
            }
            return self.async_create_entry(
                title=self._common_data[CONF_VIRTUAL_NAME],
                data=data,
            )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
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
        )

    async def async_step_codepack_type(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select a bundled codepack device type."""
        index = await self._async_get_codepack_index()
        available_types = [
            device_type for device_type in CODEPACK_DEVICE_TYPES if device_type in index
        ]
        if not available_types:
            return self.async_abort(reason="no_codepacks")

        if user_input is not None:
            self._codepack_device_type = user_input[CONF_CODEPACK_DEVICE_TYPE]
            return await self.async_step_codepack_manufacturer()

        return self.async_show_form(
            step_id="codepack_type",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CODEPACK_DEVICE_TYPE, default=available_types[0]
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=available_types,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_codepack_manufacturer(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select a bundled codepack manufacturer."""
        index = await self._async_get_codepack_index()
        manufacturers = sorted(index.get(self._codepack_device_type, {}))
        if not manufacturers:
            return self.async_abort(reason="no_codepacks")

        if user_input is not None:
            self._codepack_manufacturer = user_input[CONF_CODEPACK_MANUFACTURER]
            return await self.async_step_codepack_model()

        return self.async_show_form(
            step_id="codepack_manufacturer",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CODEPACK_MANUFACTURER, default=manufacturers[0]
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=manufacturers,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_codepack_model(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select a bundled codepack model/code id."""
        index = await self._async_get_codepack_index()
        codepacks = index[self._codepack_device_type][self._codepack_manufacturer]
        options = [
            {"value": codepack.ref, "label": codepack.label}
            for codepack in codepacks
        ]

        if user_input is not None:
            selected = next(
                codepack
                for codepack in codepacks
                if codepack.ref == user_input[CONF_CODEPACK_ID]
            )
            data = {
                **self._common_data,
                CONF_DEVICE_TYPE: self._codepack_device_type,
                CONF_CODEPACK_DEVICE_TYPE: selected.device_type,
                CONF_CODEPACK_MANUFACTURER: selected.manufacturer,
                CONF_CODEPACK_ID: selected.codepack_id,
                CONF_CODEPACK_SOURCE: selected.source,
                CONF_CODEPACK_PATH: selected.path,
            }
            return self.async_create_entry(
                title=self._common_data[CONF_VIRTUAL_NAME],
                data=data,
            )

        return self.async_show_form(
            step_id="codepack_model",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CODEPACK_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def _async_get_codepack_index(
        self,
    ) -> dict[str, dict[str, list[CodepackInfo]]]:
        """Return the bundled codepack index."""
        if self._codepack_index is None:
            custom_root = self.hass.config.path(CUSTOM_CODEPACK_DIR)
            codepacks = await self.hass.async_add_executor_job(
                discover_all_codepacks, Path(custom_root)
            )
            self._codepack_index = build_codepack_index(codepacks)
        return self._codepack_index

    async def _async_get_discovered_blasters(
        self,
    ) -> dict[str, DiscoveredIRBlaster]:
        """Return discovered Zigbee2MQTT IR blasters keyed by device ID."""
        if self._discovered_blasters is None:
            discovered = await async_discover_zigbee2mqtt_ir_blasters(self.hass)
            self._discovered_blasters = {
                blaster.device_id: blaster for blaster in discovered
            }
        return self._discovered_blasters
