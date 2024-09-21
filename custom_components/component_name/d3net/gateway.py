"""Daikin DIII-NET Interface Gateway."""

import asyncio
import logging
import time

from pymodbus.client import ModbusBaseClient

from .encoding import (
    DecodeSystemStatus,
    DecodeUnitCapability,
    DecodeUnitError,
    DecodeUnitStatus,
    Writer,
)

_LOGGER = logging.getLogger(__name__)

THROTTLE_DELAY = 0.025


class D3netGateway:
    """Daikin DIII-NET Interface Gateway."""

    def __init__(self, client: ModbusBaseClient, slave: int) -> None:
        """Initialise the D3net Gateway."""
        self._slave = slave
        self._client = client
        self._units = None
        self._throttle = None
        self._lock = asyncio.Lock()

    @property
    def units(self):
        """Return the Units."""
        return self._units

    async def _throttle_start(self):
        """Check if we need to delay and sleep."""
        if self._throttle:
            delay = time.perf_counter() - self._throttle
            if delay < THROTTLE_DELAY:
                await asyncio.sleep(THROTTLE_DELAY - delay)

    async def _throttle_end(self):
        """Register the time that we finished the last operation."""
        self._throttle = time.perf_counter()

    async def _async_connect(self):
        """Connect modbus client."""
        if not self._client.connected:
            result = await self._client.connect()
            if result:
                _LOGGER.info(
                    "Daikin Modbus connected to %s:%s",
                    self._client.comm_params.host,
                    self._client.comm_params.port,
                )
            else:
                raise ConnectionError(
                    f"Daikin Modbus unable to connect to {self._client.comm_params.host}:{self._client.comm_params.port}"
                )

    async def async_close(self):
        """Disconnect modbus client."""
        async with self._lock:
            await self._client.close()

    async def async_setup(self):
        """Return a bool array of connected units."""
        async with self._lock:
            await self._async_connect()
            if not self._units:
                self._units = []
                await self._throttle_start()
                system_status = await self._client.read_input_registers(
                    address=DecodeSystemStatus.ADDRESS,
                    count=DecodeSystemStatus.COUNT,
                    slave=self._slave,
                )
                await self._throttle_end()
                system_decoder = DecodeSystemStatus(system_status.registers)
                _LOGGER.info(
                    "System Connected: %s, Initialised: %s",
                    system_decoder.connected,
                    system_decoder.initialised,
                )

                for index, connected in enumerate(system_decoder.units_connected):
                    if connected:
                        unit = D3netUnit(self, index)
                        self._units.append(unit)

                        await self._throttle_start()
                        # _LOGGER.info("Determining capabilities for Unit %s", unit.unit_id)
                        unit_capabilities = await self._client.read_input_registers(
                            address=DecodeUnitCapability.ADDRESS
                            + index * DecodeUnitCapability.COUNT,
                            count=DecodeUnitCapability.COUNT,
                            slave=self._slave,
                        )
                        await self._throttle_end()
                        unit.capabilities = DecodeUnitCapability(
                            unit_capabilities.registers
                        )

                        await self._throttle_start()
                        # _LOGGER.info("Updating status for Unit %s", unit.unit_id)
                        unit_status = await self._client.read_input_registers(
                            address=DecodeUnitStatus.ADDRESS
                            + index * DecodeUnitStatus.COUNT,
                            count=DecodeUnitStatus.COUNT,
                            slave=self._slave,
                        )
                        await self._throttle_end()
                        unit.status = DecodeUnitStatus(unit_status.registers)

    async def async_unit_status(self, unit):
        """Fetch the status of a selected unit."""
        async with self._lock:
            await self._async_connect()
            await self._throttle_start()
            # _LOGGER.info("Updating status for Unit %s", unit.unit_id)
            unit_status = await self._client.read_input_registers(
                address=DecodeUnitStatus.ADDRESS + unit.index * DecodeUnitStatus.COUNT,
                count=DecodeUnitStatus.COUNT,
                slave=self._slave,
            )
            await self._throttle_end()
            unit.status = DecodeUnitStatus(unit_status.registers)

    async def async_write(self, address: int, values: list[int]):
        """Write a register."""
        async with self._lock:
            await self._async_connect()
            _LOGGER.info("Writing %s to address %s", values, address)
            await self._throttle_start()
            await self._client.write_registers(
                address=address, slave=self._slave, values=values
            )
            await self._throttle_end()


class D3netUnit:
    """Daikin Modbus Unit Configration."""

    def __init__(self, gateway: D3netGateway, index: int) -> None:
        """Unit Initializer."""
        self._gateway = gateway
        self._index = index
        self._capabilities: DecodeUnitCapability | None = None
        self._status: DecodeUnitStatus | None = None
        self._writer = Writer(self)

    @property
    def index(self) -> int:
        """Return unit index."""
        return self._index

    @property
    def unit_id(self) -> str:
        """Return the Daikin unit ID."""
        return f"{int(self._index/16+1)}-{self._index % 16:02d}"

    @property
    def gateway(self) -> D3netGateway:
        """Return the interface."""
        return self._gateway

    @property
    def capabilities(self) -> DecodeUnitCapability:
        """Capabilities object for the unit."""
        return self._capabilities

    @capabilities.setter
    def capabilities(self, capabilities: DecodeUnitCapability):
        """Set the capabilities object for the unit."""
        self._capabilities = capabilities

    @property
    def status(self) -> DecodeUnitStatus:
        """Status object for the unit."""
        return self._status

    @status.setter
    def status(self, status: DecodeUnitStatus):
        """Set the capabilities object for the unit."""
        self._status = status

    @property
    def error(self) -> DecodeUnitError:
        """Error object for the unit."""
        return self._error

    @error.setter
    def error(self, error: DecodeUnitError):
        """Set the Error object for the unit."""
        self._error = error

    @property
    def writer(self):
        """Writer to update settings back to unit."""
        return self._writer

    @writer.setter
    def writer(self, writer: Writer):
        """Set the Writer object for the unit."""
        self._writer = writer

    async def async_update(self):
        """Update Unit data from Gateway."""
        await self._gateway.async_unit_status(self)
