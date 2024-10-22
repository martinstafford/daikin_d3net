"""The Daikin DIII-NET Modbus integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from pymodbus.client import AsyncModbusTcpClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_SLAVE, DOMAIN, MANUFACTURER, MODEL, UPDATE_INTERVAL
from .d3net.gateway import D3netGateway, D3netUnit

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Daikin Modbus from a config entry."""
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    port = entry.data[CONF_PORT]
    slave = entry.data[CONF_SLAVE]

    _LOGGER.info("Setup %s.%s", DOMAIN, name)

    gateway = D3netGateway(
        AsyncModbusTcpClient(host=host, port=port, timeout=10), slave
    )
    await gateway.async_setup()
    entry.runtime_data = D3netCoordinator(hass, gateway, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Daikin Modbus entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if not unload_ok:
        return False

    coordinator: D3netCoordinator = entry.runtime_data
    await coordinator.gateway.async_close()

    return True


class D3netCoordinator(DataUpdateCoordinator):
    """Daikin Modbus Coordinator."""

    def __init__(
        self, hass: HomeAssistant, gateway: D3netGateway, entry: ConfigEntry
    ) -> None:
        """Initialize my coordinator."""
        self._gateway = gateway
        super().__init__(
            hass,
            _LOGGER,
            name=entry.data[CONF_NAME],
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            always_update=True,
        )

    @property
    def gateway(self):
        """The Coordinator's Gateway."""
        return self._gateway

    def device_info(self, unit: D3netUnit):
        """Return a unit based device_info block."""
        device_name = self.name + " " + unit.unit_id
        return DeviceInfo(
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=device_name,
            identifiers={(DOMAIN, device_name)},
        )

    @property
    def name(self):
        """The Integration instance name."""
        return self._name

    @name.setter
    def name(self, name):
        """Integration Instance name."""
        self._name = name

    async def _async_update_data(self):
        """Update the status of all units."""
        for unit in self._gateway.units:
            await unit.update()
