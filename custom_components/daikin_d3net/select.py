from __future__ import annotations

import logging

from homeassistant.components.climate import FAN_OFF, FAN_ON
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import D3netCoordinator
from .const import (
    FANDIRECTIONCAPABILITY_DAIKIN_HA,
    FANSPEED_DAIKIN_HA,
    FANSPEED_HA_DAIKIN,
    FANSPEEDCAPABILITY_DAIKIN_HA,
    MODE_DAIKIN_HA,
    MODE_HA_DAIKIN,
    MODE_HA_TEXT,
    MODE_TEXT_HA,
    OPERATION_MODE_ICONS,
)
from .d3net.const import D3netFanDirection
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
        if unit.capabilities.fan_speed_capable:
            entities.append(D3netSelectFanSpeed(coordinator, unit))
        if unit.capabilities.fan_direct_capable:
            entities.append(D3netSelectFanDirection(coordinator, unit))

    async_add_entities(entities)


class D3netSelectBase(CoordinatorEntity, SelectEntity):
    """Consolidation of select initialization."""

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


class D3netSelectMode(D3netSelectBase):
    """Mode Select entity."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize custom properties the mode selector."""
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
        """Icon for Operating Mode."""
        return OPERATION_MODE_ICONS[self._unit.status.operating_mode]

    async def async_select_option(self, option: str) -> None:
        """Change the selected Mode."""
        await self._unit.async_write_prepare()
        self._unit.status.operating_mode = MODE_HA_DAIKIN[MODE_TEXT_HA[option]]
        await self._unit.async_write_commit()
        self.async_write_ha_state()


class D3netSelectFanSpeed(D3netSelectBase):
    """Fan Speed Select Entity."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize custom properties for the Fan Speed selector."""
        super().__init__(coordinator, unit)
        self._attr_name = self._attr_device_info["name"] + " Fan Speed"
        self._attr_unique_id = self._attr_name
        self._attr_options = []
        for step in FANSPEEDCAPABILITY_DAIKIN_HA[unit.capabilities.fan_speed_steps]:
            if step not in (FAN_ON, FAN_OFF):
                self._attr_options.append(step.title())
        self._attr_icon = "mdi:fan"

    @property
    def current_option(self) -> str:
        """Current Fan Speed."""
        return FANSPEED_DAIKIN_HA[self._unit.status.fan_speed].title()

    async def async_select_option(self, option: str) -> None:
        """Change the Fan Speed."""
        await self._unit.async_write_prepare()
        self._unit.status.fan_speed = FANSPEED_HA_DAIKIN[option.lower()]
        await self._unit.async_write_commit()
        self.async_write_ha_state()


class D3netSelectFanDirection(D3netSelectBase):
    """Fan Direction Select Entity."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize custom properties for the Fan Direction selector."""
        super().__init__(coordinator, unit)
        self._attr_name = self._attr_device_info["name"] + " Fan Direction"
        self._attr_unique_id = self._attr_name
        self._attr_options = []
        for step in FANDIRECTIONCAPABILITY_DAIKIN_HA[
            unit.capabilities.fan_direct_steps
        ]:
            self._attr_options.append(step.name)
        self._attr_icon = "mdi:arrow-decision"

    @property
    def current_option(self) -> str:
        """Current Fan Direction."""
        return self._unit.status.fan_direct.name

    async def async_select_option(self, option: str) -> None:
        """Change the Fan Direction."""
        await self._unit.async_write_prepare()
        self._unit.status.fan_direct = D3netFanDirection[option.capitalize()]
        await self._unit.async_write_commit()
        self.async_write_ha_state()
