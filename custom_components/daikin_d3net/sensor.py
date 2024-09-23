from __future__ import annotations

import logging

from homeassistant.components.climate import HVACAction
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    UnitOfTemperature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import D3netCoordinator
from .climate import ACTION_DAIKIN_HA
from .d3net.gateway import D3netUnit
from .d3net.encoding import D3netOperationMode

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize all the Climate Entities."""
    coordinator: D3netCoordinator = entry.runtime_data
    entities = []
    for unit in coordinator.gateway.units:
        entities.append(D3netSensorTemperature(coordinator, unit))
        entities.append(D3netSensorSetpoint(coordinator, unit))
        entities.append(D3netSensorState(coordinator, unit))
    async_add_entities(entities)


class D3netSensorBase(CoordinatorEntity, SensorEntity):
    """Consolidation of sensor initialization."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize the sensor object."""
        super().__init__(coordinator, context=unit)
        self._unit = unit
        self._coordinator = coordinator
        self._attr_device_info: DeviceInfo = coordinator.device_info(unit)
        self._attr_device_name = self._attr_device_info["name"]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class D3netSensorTemperature(D3netSensorBase):
    """Sensor object for temperature data."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize custom properties for this sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_name = self._attr_device_info["name"] + " Temperature"
        self._attr_unique_id = self._attr_name
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float:
        """Current temperature in the room."""
        return self._unit.status.temp_current


class D3netSensorSetpoint(D3netSensorBase):
    """Sensor object for Setpoint data."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize custom properties for this sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_name = self._attr_device_info["name"] + " Setpoint"
        self._attr_unique_id = self._attr_name
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float:
        """Setpoint temperature in the room."""
        return self._unit.status.temp_setpoint

    @property
    def icon(self) -> str:
        """Icon for setpoint."""
        return "mdi:thermometer-check"


class D3netSensorState(D3netSensorBase):
    """Sensor object for operating state data."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize custom properties for this sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = [name for name in dir(HVACAction) if name.isupper()]
        self._attr_name = self._attr_device_info["name"] + " State"
        self._attr_unique_id = self._attr_name

    @property
    def native_value(self) -> float:
        """Current temperature in the room."""
        if self._unit.status.power:
            return ACTION_DAIKIN_HA[self._unit.status.operating_current].name
        return HVACAction.OFF.name

    @property
    def icon(self) -> str:
        """Icon for setpoint."""
        if not self._unit.status.power:
            return "mdi:power-standby"
        match self._unit.status.operating_current:
            case D3netOperationMode.FAN:
                return "mdi:fan"
            case D3netOperationMode.HEAT:
                return "mdi:fire"
            case D3netOperationMode.COOL:
                return "mdi:snowflake"
            case D3netOperationMode.DRY:
                return "mdi:water-percent"
        return "mdi:thermostat"
