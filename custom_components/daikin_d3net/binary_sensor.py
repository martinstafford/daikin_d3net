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
    entities: list[BinarySensorEntity] = [
        D3netGatewayBinaryInitialised(coordinator),
        D3netGatewayBinaryOtherDevice(coordinator),
    ]
    for unit in coordinator.gateway.units:
        entities.append(D3netBinarySensorFilter(coordinator, unit))
        entities.append(D3netBinarySensorForcedOff(coordinator, unit))
        entities.append(D3netBinarySensorError(coordinator, unit))
        entities.append(D3netBinarySensorAlarm(coordinator, unit))
        entities.append(D3netBinarySensorWarning(coordinator, unit))
        entities.append(D3netBinarySensorDefrost(coordinator, unit))
        entities.append(D3netBinarySensorCommError(coordinator, unit))
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


class D3netGatewayBinaryBase(CoordinatorEntity, BinarySensorEntity):
    """Gateway-level binary sensor."""

    def __init__(self, coordinator: D3netCoordinator) -> None:
        """Initialize the gateway binary sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_device_info = coordinator.gateway_device_info()
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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


class D3netBinarySensorForcedOff(D3netBinarySensorBase):
    """Forced-off status (T1-T2 or central forced off)."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize the forced-off sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_name = self._attr_device_info["name"] + " Forced Off"
        self._attr_unique_id = self._attr_name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:lock"

    @property
    def is_on(self) -> bool:
        """Whether the unit is forced off."""
        return self._unit.status.forced_off


class D3netBinarySensorError(D3netBinarySensorBase):
    """Unit stopped because of an error."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize the error sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_name = self._attr_device_info["name"] + " Error"
        self._attr_unique_id = self._attr_name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:alert"

    @property
    def is_on(self) -> bool:
        """Error bit from register 33602."""
        errors = self._unit.errors
        return bool(errors.error) if errors is not None else False


class D3netBinarySensorAlarm(D3netBinarySensorBase):
    """Unit alarm (unit keeps running)."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize the alarm sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_name = self._attr_device_info["name"] + " Alarm"
        self._attr_unique_id = self._attr_name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:bell-alert"

    @property
    def is_on(self) -> bool:
        """Alarm bit from register 33602."""
        errors = self._unit.errors
        return bool(errors.alarm) if errors is not None else False


class D3netBinarySensorWarning(D3netBinarySensorBase):
    """Unit warning (unit keeps running)."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize the warning sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_name = self._attr_device_info["name"] + " Warning"
        self._attr_unique_id = self._attr_name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:alert-outline"

    @property
    def is_on(self) -> bool:
        """Warning bit from register 33602."""
        errors = self._unit.errors
        return bool(errors.warning) if errors is not None else False


class D3netBinarySensorDefrost(D3netBinarySensorBase):
    """Defrost / hot start status."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize the defrost sensor."""
        super().__init__(coordinator, unit)
        self._attr_name = self._attr_device_info["name"] + " Defrost"
        self._attr_unique_id = self._attr_name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:snowflake-melt"

    @property
    def is_on(self) -> bool:
        """Defrost / hot start bit."""
        return self._unit.status.defrost


class D3netBinarySensorCommError(D3netBinarySensorBase):
    """DIII communication error for this address."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize the communication-error sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_name = self._attr_device_info["name"] + " Communication Error"
        self._attr_unique_id = self._attr_name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:lan-disconnect"

    @property
    def is_on(self) -> bool:
        """Communication error flag from system status."""
        return self._unit.communication_error


class D3netGatewayBinaryInitialised(D3netGatewayBinaryBase):
    """Modbus Interface DIII initialised / communicating."""

    def __init__(self, coordinator: D3netCoordinator) -> None:
        """Initialize the initialised sensor."""
        super().__init__(coordinator)
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_name = coordinator.name + " Interface Initialised"
        self._attr_unique_id = self._attr_name
        self._attr_icon = "mdi:check-network"

    @property
    def is_on(self) -> bool | None:
        """Adapter / DIII interface ready bit (30001 bit 0)."""
        system = self._coordinator.gateway.system
        if system is None:
            return None
        return system.initialised


class D3netGatewayBinaryOtherDevice(D3netGatewayBinaryBase):
    """Another DIII controller is present on the bus."""

    def __init__(self, coordinator: D3netCoordinator) -> None:
        """Initialize the other-device sensor."""
        super().__init__(coordinator)
        self._attr_name = coordinator.name + " Other DIII Device"
        self._attr_unique_id = self._attr_name
        self._attr_icon = "mdi:lan"

    @property
    def is_on(self) -> bool | None:
        """Other DIII device exists bit (30001 bit 1)."""
        system = self._coordinator.gateway.system
        if system is None:
            return None
        return system.other_device_exists
