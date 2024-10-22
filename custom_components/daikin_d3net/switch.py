from __future__ import annotations

import logging

from homeassistant.components.climate import HVACMode
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
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
        entities.append(D3netSwitchPower(coordinator, unit))
    async_add_entities(entities)


class D3netSwitchBase(CoordinatorEntity, SwitchEntity):
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


class D3netSwitchPower(D3netSwitchBase):
    """Binary Sensor object for filter cleaning alter."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize custom properties for this sensor."""
        super().__init__(coordinator, unit)
        self._attr_name = self._attr_device_info["name"] + " Power"
        self._attr_unique_id = self._attr_name
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:power-standby"

    @property
    def is_on(self) -> bool:
        """State of the Unit power."""
        return self._unit.status.power

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._unit.holding.power = True
        self._unit.write()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._unit.holding.power = False
        await self._unit.write()
        self.async_write_ha_state()
