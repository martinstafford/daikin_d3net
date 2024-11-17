from __future__ import annotations

import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
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
    """Initialize all the Button Entities."""
    coordinator: D3netCoordinator = entry.runtime_data
    entities = []
    for unit in coordinator.gateway.units:
        entities.append(D3netButtonFilter(coordinator, unit))
    async_add_entities(entities)


class D3netButtonBase(CoordinatorEntity, ButtonEntity):
    """Consolidation of sensor initialization."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize the sensor object."""
        super().__init__(coordinator, context=unit)
        self._unit = unit
        self._coordinator = coordinator
        self._attr_device_info: DeviceInfo = coordinator.device_info(unit)
        self._attr_device_name = self._attr_device_info["name"]


class D3netButtonFilter(D3netButtonBase):
    """Button object for filter cleaning reset."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize custom properties for this sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = ButtonDeviceClass.UPDATE
        self._attr_name = self._attr_device_info["name"] + " Filter Reset"
        self._attr_unique_id = self._attr_name

    @property
    def icon(self) -> str:
        """Icon for filter reset."""
        return "mdi:air-filter"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._unit.async_write_prepare()
        self._unit.filter_reset()
        await self._unit.async_write_commit()
