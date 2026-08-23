from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    UnitOfTemperature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import D3netCoordinator
from .const import (
    COOL_HEAT_MASTER_TEXT,
    MODE_DAIKIN_TEXT,
    OPERATION_MODE_ICONS,
    OPERATION_STATUS_TEXT,
)
from .d3net.gateway import D3netUnit

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize all the Sensor Entities."""
    coordinator: D3netCoordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    entities.append(D3netGatewaySensorConnected(coordinator))
    entities.append(D3netGatewaySensorLastErrorCode(coordinator))
    entities.append(D3netGatewaySensorLastErrorMessage(coordinator))
    entities.append(D3netGatewaySensorLastErrorUnit(coordinator))
    for unit in coordinator.gateway.units:
        entities.append(D3netSensorTemperature(coordinator, unit))
        entities.append(D3netSensorState(coordinator, unit))
        entities.append(D3netSensorErrorCode(coordinator, unit))
        entities.append(D3netSensorErrorMessage(coordinator, unit))
        entities.append(D3netSensorCoolHeatMaster(coordinator, unit))
        entities.append(D3netSensorOperationStatus(coordinator, unit))
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


class D3netGatewaySensorBase(CoordinatorEntity, SensorEntity):
    """Gateway-level diagnostic sensor."""

    def __init__(self, coordinator: D3netCoordinator) -> None:
        """Initialize the gateway sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_device_info = coordinator.gateway_device_info()
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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
        self._attr_options = list(MODE_DAIKIN_TEXT.values()) + ["Off"]
        self._attr_name = self._attr_device_info["name"] + " State"
        self._attr_unique_id = self._attr_name

    @property
    def native_value(self) -> str:
        """Current operating mode."""
        if not self._unit.status.power:
            return "Off"
        return MODE_DAIKIN_TEXT.get(self._unit.status.operating_mode, "Fan")

    @property
    def icon(self) -> str:
        """Icon for operating mode."""
        if not self._unit.status.power:
            return "mdi:power-standby"
        return OPERATION_MODE_ICONS.get(
            self._unit.status.operating_mode, "mdi:hvac"
        )


class D3netSensorErrorCode(D3netSensorBase):
    """Two-character Daikin error code from register 33601."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize the error code sensor."""
        super().__init__(coordinator, unit)
        self._attr_name = self._attr_device_info["name"] + " Error Code"
        self._attr_unique_id = self._attr_name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:alert-circle-outline"

    @property
    def native_value(self) -> str | None:
        """Current error code, or None when idle."""
        errors = self._unit.errors
        if errors is None or not errors.error_code_present:
            return None
        return errors.error_code.strip()

    @property
    def extra_state_attributes(self) -> dict:
        """Sub-code and unit number when the gateway reports them."""
        errors = self._unit.errors
        if errors is None:
            return {}
        return {
            "sub_code": errors.error_sub_code,
            "error_unit_number": errors.error_unit_number,
        }


class D3netSensorErrorMessage(D3netSensorBase):
    """Decoded error description (HomePanel DIII table)."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize the error message sensor."""
        super().__init__(coordinator, unit)
        self._attr_name = self._attr_device_info["name"] + " Error Message"
        self._attr_unique_id = self._attr_name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:message-alert-outline"

    @property
    def native_value(self) -> str | None:
        """Human-readable error text."""
        errors = self._unit.errors
        if errors is None:
            return None
        return errors.error_message


class D3netSensorCoolHeatMaster(D3netSensorBase):
    """Cool/heat master / slave / undecided."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize the master sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = list(COOL_HEAT_MASTER_TEXT.values())
        self._attr_name = self._attr_device_info["name"] + " Cool/Heat Master"
        self._attr_unique_id = self._attr_name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:crown"

    @property
    def native_value(self) -> str:
        """Master / slave / unknown."""
        return COOL_HEAT_MASTER_TEXT[self._unit.status.cool_heat_master]


class D3netSensorOperationStatus(D3netSensorBase):
    """Actual running status (fan / heating / cooling)."""

    def __init__(self, coordinator: D3netCoordinator, unit: D3netUnit) -> None:
        """Initialize the operation-status sensor."""
        super().__init__(coordinator, unit)
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = list(OPERATION_STATUS_TEXT.values())
        self._attr_name = self._attr_device_info["name"] + " Operation Status"
        self._attr_unique_id = self._attr_name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:chart-line"

    @property
    def native_value(self) -> str:
        """Actual running status."""
        return OPERATION_STATUS_TEXT.get(
            self._unit.status.operation_status, "Fan"
        )


class D3netGatewaySensorConnected(D3netGatewaySensorBase):
    """Count of DIII units the gateway reports as connected."""

    def __init__(self, coordinator: D3netCoordinator) -> None:
        """Initialize the connected-count sensor."""
        super().__init__(coordinator)
        self._attr_name = coordinator.name + " Connected Units"
        self._attr_unique_id = self._attr_name
        self._attr_icon = "mdi:counter"
        self._attr_native_unit_of_measurement = "units"

    @property
    def native_value(self) -> int | None:
        """Connected unit count."""
        system = self._coordinator.gateway.system
        if system is None:
            return None
        return system.connected_count


class D3netGatewaySensorLastErrorCode(D3netGatewaySensorBase):
    """Most recent unit error code, aggregated like HomePanel devid 0."""

    def __init__(self, coordinator: D3netCoordinator) -> None:
        """Initialize the gateway error code sensor."""
        super().__init__(coordinator)
        self._attr_name = coordinator.name + " Last Error Code"
        self._attr_unique_id = self._attr_name
        self._attr_icon = "mdi:alert-circle"

    @property
    def native_value(self) -> str | None:
        """Last error code across all units."""
        code, _, _ = self._coordinator.gateway.last_error
        return code


class D3netGatewaySensorLastErrorMessage(D3netGatewaySensorBase):
    """Description of the aggregated last error."""

    def __init__(self, coordinator: D3netCoordinator) -> None:
        """Initialize the gateway error message sensor."""
        super().__init__(coordinator)
        self._attr_name = coordinator.name + " Last Error Message"
        self._attr_unique_id = self._attr_name
        self._attr_icon = "mdi:message-alert"

    @property
    def native_value(self) -> str | None:
        """Last error message across all units."""
        _, message, _ = self._coordinator.gateway.last_error
        return message


class D3netGatewaySensorLastErrorUnit(D3netGatewaySensorBase):
    """Which indoor unit produced the aggregated last error."""

    def __init__(self, coordinator: D3netCoordinator) -> None:
        """Initialize the gateway error unit sensor."""
        super().__init__(coordinator)
        self._attr_name = coordinator.name + " Last Error Unit"
        self._attr_unique_id = self._attr_name
        self._attr_icon = "mdi:identifier"

    @property
    def native_value(self) -> str | None:
        """Unit id of the last error."""
        _, _, unit_id = self._coordinator.gateway.last_error
        return unit_id
