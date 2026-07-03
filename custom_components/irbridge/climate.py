"""Climate platform for IRBridge."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .bridge import IRBridgeDevice
from .codepacks import ClimateCodepack, parse_climate_codepack
from .codepacks import resolve_climate_command
from .const import (
    CONF_CODEPACK_DEVICE_TYPE,
    CONF_CODEPACK_ID,
    CONF_DEVICE_TYPE,
    CONF_SETUP_MODE,
    DEVICE_TYPE_CLIMATE,
    DOMAIN,
    SETUP_MODE_CODEPACK,
)

_LOGGER = logging.getLogger(__name__)

SMARTIR_TO_HVAC_MODE = {
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "dry": HVACMode.DRY,
    "fan": HVACMode.FAN_ONLY,
    "fan_only": HVACMode.FAN_ONLY,
    "auto": HVACMode.AUTO,
}
HVAC_TO_SMARTIR_MODE = {
    HVACMode.COOL: "cool",
    HVACMode.HEAT: "heat",
    HVACMode.DRY: "dry",
    HVACMode.FAN_ONLY: "fan_only",
    HVACMode.AUTO: "auto",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IRBridge climate entities."""
    if entry.data.get(CONF_SETUP_MODE) != SETUP_MODE_CODEPACK:
        return
    if entry.data.get(CONF_DEVICE_TYPE) != DEVICE_TYPE_CLIMATE:
        return
    if entry.data.get(CONF_CODEPACK_DEVICE_TYPE) != DEVICE_TYPE_CLIMATE:
        return

    codepack_id = entry.data.get(CONF_CODEPACK_ID)
    if not codepack_id:
        _LOGGER.warning("Skipping IRBridge climate entity with no codepack id")
        return

    bridge_device: IRBridgeDevice = hass.data[DOMAIN][entry.entry_id]
    try:
        codepack_data = await hass.async_add_executor_job(
            bridge_device.load_selected_codepack
        )
        climate_codepack = parse_climate_codepack(codepack_data)
    except HomeAssistantError:
        _LOGGER.warning(
            "Skipping invalid IRBridge climate codepack",
            extra={"entry_id": entry.entry_id, "codepack_id": codepack_id},
            exc_info=True,
        )
        return

    bridge_device._codepack_data = codepack_data
    try:
        climate_entity = IRBridgeClimateEntity(bridge_device, climate_codepack)
    except HomeAssistantError:
        _LOGGER.warning(
            "Skipping IRBridge climate entity with unsupported codepack",
            extra={"entry_id": entry.entry_id, "codepack_id": codepack_id},
            exc_info=True,
        )
        return

    async_add_entities([climate_entity])


class IRBridgeClimateEntity(RestoreEntity, ClimateEntity):
    """Assumed-state SmartIR-compatible IR climate entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self, bridge_device: IRBridgeDevice, climate_codepack: ClimateCodepack
    ) -> None:
        """Initialize the climate entity."""
        self._bridge_device = bridge_device
        self._codepack = climate_codepack
        self._attr_unique_id = f"{bridge_device.entry.entry_id}_climate"
        self._attr_device_info = bridge_device.device_info
        self._attr_min_temp = climate_codepack.min_temperature
        self._attr_max_temp = climate_codepack.max_temperature
        self._attr_target_temperature_step = climate_codepack.precision
        self._attr_precision = climate_codepack.precision
        self._attr_hvac_modes = self._build_hvac_modes(climate_codepack)
        self._attr_fan_modes = (
            list(climate_codepack.fan_modes)
            if _has_matching_mode_keys(
                climate_codepack.commands, climate_codepack.fan_modes
            )
            else None
        )
        self._attr_swing_modes = (
            list(climate_codepack.swing_modes)
            if _has_matching_mode_keys(
                climate_codepack.commands, climate_codepack.swing_modes
            )
            else None
        )
        self._attr_supported_features = self._build_supported_features(
            climate_codepack
        )

        self._hvac_mode = self._default_on_mode()
        self._last_on_mode = self._hvac_mode
        self._target_temperature = self._default_temperature()
        self._fan_mode = self._default_fan_mode()
        self._swing_mode = self._default_swing_mode()

    async def async_added_to_hass(self) -> None:
        """Restore assumed climate state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        try:
            restored_hvac_mode = HVACMode(last_state.state)
        except ValueError:
            restored_hvac_mode = None

        if restored_hvac_mode in self.hvac_modes:
            self._hvac_mode = restored_hvac_mode
            if restored_hvac_mode != HVACMode.OFF:
                self._last_on_mode = restored_hvac_mode

        temperature = last_state.attributes.get(ATTR_TEMPERATURE)
        if isinstance(temperature, (int, float)):
            self._target_temperature = float(temperature)
        fan_mode = last_state.attributes.get("fan_mode")
        if fan_mode in (self.fan_modes or []):
            self._fan_mode = fan_mode
        swing_mode = last_state.attributes.get("swing_mode")
        if swing_mode in (self.swing_modes or []):
            self._swing_mode = swing_mode

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current assumed HVAC mode."""
        return self._hvac_mode

    @property
    def target_temperature(self) -> float:
        """Return the current assumed target temperature."""
        return self._target_temperature

    @property
    def fan_mode(self) -> str | None:
        """Return the current assumed fan mode."""
        return self._fan_mode

    @property
    def swing_mode(self) -> str | None:
        """Return the current assumed swing mode."""
        return self._swing_mode

    async def async_turn_off(self) -> None:
        """Turn the IR climate device off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        """Turn the IR climate device on using a sensible mode."""
        if self._hvac_mode != HVACMode.OFF:
            return
        await self.async_set_hvac_mode(self._last_on_mode or self._default_on_mode())

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a new HVAC mode."""
        if hvac_mode not in self.hvac_modes:
            raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
        await self._async_send_state(hvac_mode)
        self._hvac_mode = hvac_mode
        if hvac_mode != HVACMode.OFF:
            self._last_on_mode = hvac_mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        hvac_mode = kwargs.get("hvac_mode", self._hvac_mode)
        if isinstance(hvac_mode, str):
            hvac_mode = HVACMode(hvac_mode)
        if hvac_mode == HVACMode.OFF:
            hvac_mode = self._last_on_mode or self._default_on_mode()
        target_temperature = float(temperature)
        await self._async_send_state(hvac_mode, target_temperature=target_temperature)
        self._hvac_mode = hvac_mode
        self._last_on_mode = hvac_mode
        self._target_temperature = target_temperature
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set a new fan mode."""
        if fan_mode not in (self.fan_modes or []):
            raise HomeAssistantError(f"Unsupported fan mode: {fan_mode}")
        hvac_mode = self._hvac_mode
        if hvac_mode == HVACMode.OFF:
            hvac_mode = self._last_on_mode or self._default_on_mode()
        await self._async_send_state(hvac_mode, fan_mode=fan_mode)
        self._hvac_mode = hvac_mode
        self._last_on_mode = hvac_mode
        self._fan_mode = fan_mode
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set a new swing mode."""
        if swing_mode not in (self.swing_modes or []):
            raise HomeAssistantError(f"Unsupported swing mode: {swing_mode}")
        hvac_mode = self._hvac_mode
        if hvac_mode == HVACMode.OFF:
            hvac_mode = self._last_on_mode or self._default_on_mode()
        await self._async_send_state(hvac_mode, swing_mode=swing_mode)
        self._hvac_mode = hvac_mode
        self._last_on_mode = hvac_mode
        self._swing_mode = swing_mode
        self.async_write_ha_state()

    async def _async_send_state(
        self,
        hvac_mode: HVACMode,
        *,
        target_temperature: float | None = None,
        fan_mode: str | None = None,
        swing_mode: str | None = None,
    ) -> None:
        """Resolve and send the IR command for a desired climate state."""
        operation_mode = (
            "off" if hvac_mode == HVACMode.OFF else HVAC_TO_SMARTIR_MODE[hvac_mode]
        )
        resolved_code = resolve_climate_command(
            self._bridge_device._codepack_data or {},
            operation_mode,
            target_temperature
            if target_temperature is not None
            else self._target_temperature,
            fan_mode if fan_mode is not None else self._fan_mode,
            swing_mode if swing_mode is not None else self._swing_mode,
        )
        await self._bridge_device.async_send_ir_code(resolved_code)

    def _default_temperature(self) -> float:
        """Return a safe default target temperature."""
        if self._codepack.default_temperature is not None:
            return self._clamp_temperature(self._codepack.default_temperature)
        if self.min_temp <= 22 <= self.max_temp:
            return 22.0
        return self.min_temp

    def _clamp_temperature(self, temperature: float) -> float:
        """Clamp temperature to the codepack range."""
        return max(self.min_temp, min(self.max_temp, float(temperature)))

    def _default_fan_mode(self) -> str | None:
        """Return the default fan mode."""
        return self.fan_modes[0] if self.fan_modes else None

    def _default_swing_mode(self) -> str | None:
        """Return the default swing mode."""
        return self.swing_modes[0] if self.swing_modes else None

    def _default_on_mode(self) -> HVACMode:
        """Return the preferred mode to use when turning on."""
        for hvac_mode in (HVACMode.COOL, HVACMode.AUTO):
            if hvac_mode in self.hvac_modes:
                return hvac_mode
        return next(mode for mode in self.hvac_modes if mode != HVACMode.OFF)

    @staticmethod
    def _build_hvac_modes(climate_codepack: ClimateCodepack) -> list[HVACMode]:
        """Build supported HVAC modes from SmartIR operation modes and commands."""
        modes: list[HVACMode] = []
        if isinstance(climate_codepack.commands.get("off"), str):
            modes.append(HVACMode.OFF)
        for operation_mode in climate_codepack.operation_modes:
            hvac_mode = SMARTIR_TO_HVAC_MODE.get(operation_mode)
            if hvac_mode is not None and hvac_mode not in modes:
                modes.append(hvac_mode)
        if len(modes) == 1 and modes[0] == HVACMode.OFF:
            raise HomeAssistantError("Climate codepack has no supported on modes")
        if not modes:
            raise HomeAssistantError("Climate codepack has no supported HVAC modes")
        return modes

    @staticmethod
    def _build_supported_features(
        climate_codepack: ClimateCodepack,
    ) -> ClimateEntityFeature:
        """Build supported climate feature flags from codepack data."""
        features = ClimateEntityFeature(0)
        if climate_codepack.has_temperature_commands:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if _has_matching_mode_keys(
            climate_codepack.commands, climate_codepack.fan_modes
        ):
            features |= ClimateEntityFeature.FAN_MODE
        if _has_matching_mode_keys(
            climate_codepack.commands, climate_codepack.swing_modes
        ):
            features |= ClimateEntityFeature.SWING_MODE
        if hasattr(ClimateEntityFeature, "TURN_ON"):
            features |= ClimateEntityFeature.TURN_ON
        if hasattr(ClimateEntityFeature, "TURN_OFF"):
            features |= ClimateEntityFeature.TURN_OFF
        return features


def _tree_contains_key(node: Any, expected_key: str) -> bool:
    """Return whether a nested command tree contains a key."""
    if not isinstance(node, dict):
        return False
    for key, value in node.items():
        if str(key) == expected_key:
            return True
        if _tree_contains_key(value, expected_key):
            return True
    return False


def _has_matching_mode_keys(node: Any, modes: tuple[str, ...]) -> bool:
    """Return whether any advertised mode exists in the command tree."""
    return any(_tree_contains_key(node, mode) for mode in modes)
