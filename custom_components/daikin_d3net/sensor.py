from __future__ import annotations

import logging

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
from .const import MODE_DAIKIN_HA, MODE_HA_TEXT, OPERATION_MODE_ICONS
from .d3net.gateway import D3netUnit

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize all the Climate Entities."""
    coordinator: D3netCoordinator = entry.runtime_data
    entities = []
    for unit in coordinator.gateway.units:
        entities.append(D3netSensorTemperature(coordinator, unit))
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


class D3netSensorState(D3netSensorBase):
    """Sensor object for operating state data."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize custom properties for this sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = [MODE_HA_TEXT[name] for name in MODE_HA_TEXT]
        self._attr_options.append("Off")
        self._attr_name = self._attr_device_info["name"] + " State"
        self._attr_unique_id = self._attr_name

    @property
    def native_value(self) -> str:
        """Current operating mode."""
        return (
            MODE_HA_TEXT[MODE_DAIKIN_HA[self._unit.status.operating_mode]]
            if self._unit.status.power
            else "Off"
        )

    @property
    def icon(self) -> str:
        """Icon for operating mode."""
        if not self._unit.status.power:
            return "mdi:power-standby"
        return OPERATION_MODE_ICONS[self._unit.status.operating_mode]
