from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
    """Initialize all the Binary Sensor Entities."""
    coordinator: D3netCoordinator = entry.runtime_data
    entities = []
    for unit in coordinator.gateway.units:
        entities.append(D3netBinarySensorFilter(coordinator, unit))
    async_add_entities(entities)


class D3netBinarySensorBase(CoordinatorEntity, BinarySensorEntity):
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


class D3netBinarySensorFilter(D3netBinarySensorBase):
    """Binary Sensor object for filter cleaning alter."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize custom properties for this sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_name = self._attr_device_info["name"] + " Filter Warning"
        self._attr_unique_id = self._attr_name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """State of the Clean Filter warning."""
        return self._unit.status.filter_warning

    @property
    def icon(self) -> str:
        """Icon for filter warning."""
        return "mdi:air-filter"
