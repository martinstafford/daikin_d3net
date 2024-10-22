"""Daikin Modbus Climate Entity."""

from __future__ import annotations

import logging

from homeassistant.components.climate import (
    FAN_OFF,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    UnitOfTemperature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import D3netCoordinator
from .const import (
    FANSPEED_DAIKIN_HA,
    FANSPEED_HA_DAIKIN,
    FANSPEEDCAPABILITY_DAIKIN_HA,
    OPERATION_MODE_ICONS,
)
from .d3net.encoding import D3netOperationMode
from .d3net.gateway import D3netUnit

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize all the Climate Entities."""
    coordinator: D3netCoordinator = entry.runtime_data
    entities = [D3netClimate(coordinator, unit) for unit in coordinator.gateway.units]
    async_add_entities(entities)


MODE_DAIKIN_HA = {
    D3netOperationMode.AUTO: HVACMode.AUTO,
    D3netOperationMode.COOL: HVACMode.COOL,
    D3netOperationMode.DRY: HVACMode.DRY,
    D3netOperationMode.FAN: HVACMode.FAN_ONLY,
    D3netOperationMode.HEAT: HVACMode.HEAT,
}
MODE_HA_DAIKIN = {
    HVACMode.AUTO: D3netOperationMode.AUTO,
    HVACMode.COOL: D3netOperationMode.COOL,
    HVACMode.DRY: D3netOperationMode.DRY,
    HVACMode.FAN_ONLY: D3netOperationMode.FAN,
    HVACMode.HEAT: D3netOperationMode.HEAT,
}
MODE_HA_TEXT = {
    HVACMode.AUTO: "Auto",
    HVACMode.COOL: "Cool",
    HVACMode.DRY: "Dry",
    HVACMode.FAN_ONLY: "Fan",
    HVACMode.HEAT: "Heat",
    HVACMode.OFF: "Off",
}

ACTION_DAIKIN_HA = {
    D3netOperationMode.HEAT: HVACAction.HEATING,
    D3netOperationMode.COOL: HVACAction.COOLING,
    D3netOperationMode.FAN: HVACAction.FAN,
}


class D3netClimate(CoordinatorEntity, ClimateEntity):
    """Daikin Modbus Climate Entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Daikin Modbus Climate Entity Initialization."""
        super().__init__(coordinator, context=unit)
        self._unit = unit
        self._coordinator = coordinator

        self._attr_device_info: DeviceInfo = coordinator.device_info(unit)
        self._attr_name = self._attr_device_info["name"]
        self._attr_unique_id = self._attr_name

        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            if unit.capabilities.fan_speed_capable
            else 0 | ClimateEntityFeature.SWING_MODE
            if unit.capabilities.fan_direct_capable
            else 0
        )

        self.hvac_modes = []
        self.hvac_modes.append(HVACMode.OFF)
        if unit.capabilities.cool_mode_capable:
            self.hvac_modes.append(HVACMode.COOL)
        if unit.capabilities.heat_mode_capable:
            self.hvac_modes.append(HVACMode.HEAT)
        if unit.capabilities.auto_mode_capable:
            self.hvac_modes.append(HVACMode.AUTO)
        if unit.capabilities.dry_mode_capable:
            self.hvac_modes.append(HVACMode.DRY)
        if unit.capabilities.fan_mode_capable:
            self.hvac_modes.append(HVACMode.FAN_ONLY)

        if unit.capabilities.fan_speed_capable:
            self.fan_modes = FANSPEEDCAPABILITY_DAIKIN_HA[
                unit.capabilities.fan_speed_steps
            ]

    @property
    def icon(self) -> str:
        """Icon for setpoint."""
        if not self._unit.status.power:
            return "mdi:power-standby"
        return OPERATION_MODE_ICONS[self._unit.status.operating_mode]

    @property
    def max_temp(self) -> float:
        """Maximum Temperature."""
        return self._unit.capabilities.heat_setpoint_upperlimit

    @property
    def min_temp(self) -> float:
        """Minimum Temperature."""
        return self._unit.capabilities.cool_setpoint_lowerlimit

    @property
    def hvac_mode(self) -> HVACMode:
        """The HVAC mode that Unit is in."""
        if self._unit.status.power:
            return MODE_DAIKIN_HA[self._unit.status.operating_mode]
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """The HVAC mode that Unit is in."""
        if self._unit.status.power:
            return ACTION_DAIKIN_HA[self._unit.status.operating_current]
        return HVACAction.OFF

    @property
    def current_temperature(self) -> float | None:
        """Current room temperature."""
        return self._unit.status.temp_current

    @property
    def target_temperature(self) -> float | None:
        """Target room temperature."""
        return self._unit.status.temp_setpoint

    @property
    def fan_mode(self):
        """Target room temperature."""
        if self._unit.status.fan:
            return FANSPEED_DAIKIN_HA[self._unit.status.fan_speed]
        return FAN_OFF

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn on the unit."""
        await self._unit.async_write_prepare()
        self._unit.status.power = True
        await self._unit.async_write_commit()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off the unit."""
        await self._unit.async_write_prepare()
        self._unit.status.power = False
        await self._unit.async_write_commit()
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        await self._unit.async_write_prepare()
        if hvac_mode is HVACMode.OFF:
            self._unit.status.power = False
        else:
            self._unit.status.power = True
            self._unit.status.operating_mode = MODE_HA_DAIKIN[hvac_mode]
        await self._unit.async_write_commit()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        await self._unit.async_write_prepare()
        self._unit.status.temp_setpoint = kwargs["temperature"]
        await self._unit.async_write_commit()
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        await self._unit.async_write_prepare()
        self._unit.status.fan_speed = FANSPEED_HA_DAIKIN[fan_mode]
        await self._unit.async_write_commit()
        self.async_write_ha_state()
