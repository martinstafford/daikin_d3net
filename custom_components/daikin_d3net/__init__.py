"""The Daikin DIII-NET Modbus integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.framer import FramerType as ModbusFramer

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_PROTOCOL,
    CONF_SLAVE,
    DOMAIN,
    MANUFACTURER,
    MODBUS_RETRIES,
    MODBUS_TIMEOUT,
    MODEL,
    PROTOCOL_RTU_OVER_TCP,
    PROTOCOL_TCP,
    UPDATE_INTERVAL,
)
from .d3net.gateway import UPDATE_TIMEOUT, D3netGateway, D3netUnit

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
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
    protocol = entry.data.get(CONF_PROTOCOL, PROTOCOL_TCP)

    _LOGGER.info("Setup %s.%s", DOMAIN, name)

    def client_factory() -> AsyncModbusTcpClient:
        """Build a fresh modbus client.

        The gateway calls this again whenever it has discarded a client after a
        communications failure, so a restarted modbus gateway is picked up on
        the next poll without reloading the config entry.
        """
        if protocol == PROTOCOL_RTU_OVER_TCP:
            return AsyncModbusTcpClient(
                host=host,
                port=port,
                timeout=MODBUS_TIMEOUT,
                retries=MODBUS_RETRIES,
                framer=ModbusFramer.RTU,
            )
        return AsyncModbusTcpClient(
            host=host,
            port=port,
            timeout=MODBUS_TIMEOUT,
            retries=MODBUS_RETRIES,
        )

    gateway = D3netGateway(client_factory, slave)
    try:
        await gateway.async_setup()
        entry.runtime_data = D3netCoordinator(hass, gateway, entry)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except ConnectionError as ex:
        raise ConfigEntryNotReady(f"Unable to connect to {host}:{port}") from ex
    else:
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
        try:
            async with asyncio.timeout(UPDATE_TIMEOUT):
                for unit in self._gateway.units:
                    await unit.async_update_status()
        except TimeoutError as ex:
            # Cancelled mid request, so the connection state is unknown.
            # Drop it rather than reusing it on the next poll.
            await self._gateway.async_disconnect()
            raise UpdateFailed(
                f"Timed out after {UPDATE_TIMEOUT} seconds polling the Daikin gateway"
            ) from ex
        except (ConnectionError, ModbusException) as ex:
            # A single clean warning and an automatic retry on the next poll.
            # Entities go unavailable until a poll reconnects successfully.
            raise UpdateFailed(f"Error communicating with Daikin gateway: {ex}") from ex
        finally:
            # Close connection after each update to prevent timeouts
            await self._gateway.async_close()
