from __future__ import annotations

import logging

from homeassistant.components.climate import HVACMode
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import D3netCoordinator
from .const import (
    MODE_DAIKIN_HA,
    MODE_HA_DAIKIN,
    MODE_HA_TEXT,
    MODE_TEXT_HA,
    OPERATION_MODE_ICONS,
)
from .d3net.gateway import D3netUnit

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize all the Climate Entities."""
    coordinator: D3netCoordinator = entry.runtime_data
    entities = []
    for unit in coordinator.gateway.units:
        entities.append(D3netSelectMode(coordinator, unit))
    async_add_entities(entities)


class D3netSensorBase(CoordinatorEntity, SelectEntity):
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


class D3netSelectMode(D3netSensorBase):
    """Binary Sensor object for filter cleaning alter."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize custom properties for this sensor."""
        super().__init__(coordinator, unit)
        self._attr_name = self._attr_device_info["name"] + " Mode"
        self._attr_unique_id = self._attr_name
        self._attr_options = [MODE_HA_TEXT[name] for name in MODE_HA_TEXT]

    @property
    def current_option(self) -> str:
        """Current Operating Mode."""
        return MODE_HA_TEXT[MODE_DAIKIN_HA[self._unit.status.operating_mode]]

    @property
    def icon(self) -> str:
        """Icon for setpoint."""
        return OPERATION_MODE_ICONS[self._unit.status.operating_mode]

    async def async_select_option(self, option: str) -> None:
        """Change the selected Mode."""
        await self._unit.writer.write(
            operating_mode=MODE_HA_DAIKIN[MODE_TEXT_HA[option]]
        )
