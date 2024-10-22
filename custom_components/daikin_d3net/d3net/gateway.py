"""Daikin DIII-NET Interface Gateway."""

import asyncio
import logging
import time

from pymodbus.client import ModbusBaseClient
from pymodbus.pdu import ModbusResponse

from .const import D3netRegisterType
from .encoding import (
    HoldingBase,
    InputBase,
    SystemStatus,
    UnitCapability,
    UnitError,
    UnitHolding,
    UnitStatus,
)

_LOGGER = logging.getLogger(__name__)

# Seconds between modbus access
THROTTLE_DELAY = 0.025
# Seconds before we read from a unit after writing to it
CACHE_WRITE = 5
# Seconds before we reload status information
CACHE_READ = 60
# Seconds before we reload error information
CACHE_ERROR = 10


class D3netGateway:
    """Daikin DIII-NET Interface Gateway."""

    def __init__(self, client: ModbusBaseClient, slave: int) -> None:
        """Initialise the D3net Gateway."""
        self._slave = slave
        self._client: ModbusBaseClient = client
        self._units: D3netUnit | None = None
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
                system_decoder: SystemStatus = await self._async_read(SystemStatus)
                _LOGGER.info(
                    "System Connected: %s, Initialised: %s",
                    system_decoder.connected,
                    system_decoder.initialised,
                )

                for index, connected in enumerate(system_decoder.units_connected):
                    if connected:
                        capabilities: UnitCapability = await self._async_read(
                            UnitCapability, index
                        )
                        unit = D3netUnit(self, index, capabilities)
                        self._units.append(unit)

        # Update the unit status outside of the lock
        for unit in self._units:
            await unit.async_update_status()

    async def async_read(self, Decoder: type[InputBase], index: int = 0) -> InputBase:
        """Load registers and return a decode object."""
        async with self._lock:
            await self._async_connect()
            return await self._async_read(Decoder, index)

    async def _async_read(self, Decoder: type[InputBase], index: int = 0) -> InputBase:
        """Load registers and return a decode object. Must already hold a lock and connection."""
        await self._throttle_start()
        response: ModbusResponse = None
        address = Decoder.ADDRESS + index * Decoder.COUNT
        if Decoder.TYPE == D3netRegisterType.Holding:
            response = await self._client.read_holding_registers(
                address=address,
                count=Decoder.COUNT,
                slave=self._slave,
            )
        else:
            response = await self._client.read_input_registers(
                address=address,
                count=Decoder.COUNT,
                slave=self._slave,
            )
        await self._throttle_end()
        return Decoder(response.registers)

    async def async_write(self, decode: HoldingBase, index: int):
        """Write a register."""
        if decode.dirty:
            async with self._lock:
                await self._async_connect()
                await self._throttle_start()
                address = decode.ADDRESS + index * decode.COUNT
                _LOGGER.info("Writing %s to address %s", decode.registers, address)
                await self._client.write_registers(
                    address=address, slave=self._slave, values=decode.registers
                )
                await self._throttle_end()
                decode.written()


class D3netUnit:
    """Daikin Modbus Unit Configration."""

    SYNC_PROPERTIES = [
        "power",
        "fan_direct",
        "fan_speed",
        "operating_mode",
        "temp_setpoint",
        "filter_warning",
    ]

    def __init__(
        self, gateway: D3netGateway, index: int, capabilities: UnitCapability
    ) -> None:
        """Unit Initializer."""
        self._gateway = gateway
        self._index = index
        self._capabilities: UnitCapability = capabilities
        self._status: UnitStatus | None = None
        self._holding: UnitHolding | None = None
        self._error: UnitError | None = None

    @property
    def index(self) -> int:
        """Return unit index."""
        return self._index

    @property
    def unit_id(self) -> str:
        """Return the Daikin unit ID."""
        return f"{int(self._index/16+1)}-{self._index % 16:02d}"

    @property
    def capabilities(self) -> UnitCapability:
        """Capabilities object for the unit."""
        return self._capabilities

    @property
    def status(self) -> UnitStatus:
        """Status object for the unit."""
        return self._status

    @property
    def errors(self) -> UnitError:
        """Error object for the unit."""
        if self._error is None or not self._holding.readWithin(CACHE_ERROR):
            self._error = self._gateway.async_read(UnitError, self._index)
        return self._error

    async def async_update_status(self):
        """Load unit status"""
        # Don't update status if we've just written
        if self._holding is None or not self._holding.writeWithin(CACHE_WRITE):
            self._status = await self._gateway.async_read(UnitStatus, self._index)

    async def async_write_prepare(self):
        """Prepare the holding registers for a write by reading them and making sure they match the current status."""
        # Only reload holding if it's not dirty and older than CACHE_WRITE, otherwise assume we're authorative.
        if self._holding is None or (
            not self._holding.dirty
            and not self._holding.readWithin(CACHE_WRITE)
            and not self._holding.writeWithin(CACHE_WRITE)
        ):
            self._holding = await self._gateway.async_read(UnitHolding, self._index)
            reg = self._holding.registers
            self._holding.sync(self._status, self.SYNC_PROPERTIES)
            if self._holding.dirty:
                # The holding registers are out of sync with status, so update them before making changes.
                # This is the whole point of doing a Prepare.
                _LOGGER.info(
                    "Holding out of sync. Holding: %s, Status: %s ", reg, self._holding
                )
                await self._gateway.async_write(self._holding, self._index)

    async def async_write_commit(self):
        """Write any dirty holding registers."""
        # Copy the updated status registers into the holding registers
        self._holding.sync(self._status, self.SYNC_PROPERTIES)
        # They'll only write if there was something made dirty
        await self._gateway.async_write(self._holding, self._index)
