from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.components.sensor import UnitOfTemperature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import D3netCoordinator
from .d3net.gateway import D3netUnit

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize all the Climate Entities."""
    coordinator: D3netCoordinator = entry.runtime_data
    entities = []
    for unit in coordinator.gateway.units:
        entities.append(D3netNumberSetpoint(coordinator, unit))
    async_add_entities(entities)


class D3netNumberBase(CoordinatorEntity, NumberEntity):
    """Consolidation of number initialization."""

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


class D3netNumberSetpoint(D3netNumberBase):
    """Binary Sensor object for filter cleaning alter."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize custom properties for this sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = NumberDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_mode = NumberMode.BOX
        self._attr_icon = "mdi:thermometer-check"
        self._attr_name = self._attr_device_info["name"] + " Setpoint"
        self._attr_unique_id = self._attr_name
        self._attr_native_min_value = 10
        self._attr_native_max_value = 30
        self._attr_native_step = 0.1

    @property
    def native_value(self) -> float:
        """Setpoint temperature in the room."""
        return self._unit.status.temp_setpoint

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._unit.holding.temp_setpoint = value
        await self._unit.write()
        self.async_write_ha_state()
