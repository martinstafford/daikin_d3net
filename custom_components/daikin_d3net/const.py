"""Constants for the Daikin DIII-NET Modbus integration."""

from homeassistant.components.climate import HVACMode, HVACAction

from .d3net.encoding import D3netOperationMode

DOMAIN = "daikin_d3net"
MANUFACTURER = "Daikin"
MODEL = "DIII-Net Modbus"

CONF_SLAVE = "d3net_slave"

DEFAULT_NAME = "Daikin"
DEFAULT_PORT = 502
DEFAULT_SLAVE = 1

UPDATE_INTERVAL = 30

OPERATION_MODE_ICONS = {
    D3netOperationMode.FAN: "mdi:fan",
    D3netOperationMode.HEAT: "mdi:fire",
    D3netOperationMode.COOL: "mdi:snowflake",
    D3netOperationMode.DRY: "mdi:water-percent",
    D3netOperationMode.AUTO: "mdi:thermostat-auto",
    D3netOperationMode.VENT: "mdi:weather-windy",
}

MODE_DAIKIN_HA = {
    D3netOperationMode.AUTO: HVACMode.AUTO,
    D3netOperationMode.COOL: HVACMode.COOL,
    D3netOperationMode.DRY: HVACMode.DRY,
    D3netOperationMode.FAN: HVACMode.FAN_ONLY,
    D3netOperationMode.HEAT: HVACMode.HEAT,
}

MODE_HA_DAIKIN = {
    HVACMode.AUTO: D3netOperationMode.AUTO,
    HVACMode.COOL: D3netOperationMode.COOL,
    HVACMode.DRY: D3netOperationMode.DRY,
    HVACMode.FAN_ONLY: D3netOperationMode.FAN,
    HVACMode.HEAT: D3netOperationMode.HEAT,
}

MODE_HA_TEXT = {
    HVACMode.AUTO: "Auto",
    HVACMode.COOL: "Cool",
    HVACMode.DRY: "Dry",
    HVACMode.FAN_ONLY: "Fan",
    HVACMode.HEAT: "Heat",
    # HVACMode.OFF: "Off",
}

MODE_TEXT_HA = {
    "Auto": HVACMode.AUTO,
    "Cool": HVACMode.COOL,
    "Dry": HVACMode.DRY,
    "Fan": HVACMode.FAN_ONLY,
    "Heat": HVACMode.HEAT,
    # "Off": HVACMode.OFF,
}

ACTION_DAIKIN_HA = {
    D3netOperationMode.HEAT: HVACAction.HEATING,
    D3netOperationMode.COOL: HVACAction.COOLING,
    D3netOperationMode.FAN: HVACAction.FAN,
}
