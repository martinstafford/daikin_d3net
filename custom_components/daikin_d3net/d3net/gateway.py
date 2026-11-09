"""Daikin DIII-NET Interface Gateway."""

import asyncio
from collections.abc import Callable
import logging
import time

from pymodbus.client import ModbusBaseClient
from pymodbus.exceptions import ModbusException

# from pymodbus.pdu import ModbusResponse
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
# Seconds before we read from a unit after writing to it.
# This is how long we don't care what manual changes are made on the panel and we'll overwrite them.
# The fan speed change takes a long time to propagate back to the modbus gateway so needs to be this high.
CACHE_WRITE = 35
# Seconds before we reload status information
CACHE_READ = 60
# Seconds before we reload error information
CACHE_ERROR = 10
# Seconds allowed for a complete poll of every unit.
# pymodbus bounds each individual request at MODBUS_TIMEOUT * (MODBUS_RETRIES + 1),
# but a gateway that accepts a connection and then never answers would stall a
# poll for that long *per unit* - minutes on a large install. Capping the whole
# poll keeps entity availability responsive.
UPDATE_TIMEOUT = 30
# Seconds allowed for unit discovery, which reads two registers per connected unit.
SETUP_TIMEOUT = 90


class D3netGateway:
    """Daikin DIII-NET Interface Gateway."""

    def __init__(
        self, client_factory: Callable[[], ModbusBaseClient], device_id: int
    ) -> None:
        """Initialise the D3net Gateway.

        client_factory is called to build a modbus client. A new client is built
        whenever the previous one has been discarded after a communications
        failure, so that a restarted gateway is picked up on the next poll.
        """
        self._device_id = device_id
        self._client_factory = client_factory
        self._client: ModbusBaseClient | None = None
        self._units: D3netUnit | None = None
        self._throttle = None
        self._lock = asyncio.Lock()

    @property
    def units(self):
        """Return the Units."""
        return self._units

    @property
    def connected(self) -> bool:
        """Whether we currently hold a connection to the gateway."""
        return self._client is not None and self._client.connected

    async def _throttle_start(self):
        """Check if we need to delay and sleep."""
        if self._throttle:
            delay = time.perf_counter() - self._throttle
            if delay < THROTTLE_DELAY:
                await asyncio.sleep(THROTTLE_DELAY - delay)

    async def _throttle_end(self):
        """Register the time that we finished the last operation."""
        self._throttle = time.perf_counter()

    def _discard_client(self):
        """Throw away the current client after a failure.

        The next connection attempt then starts from a clean client, which is
        what allows us to recover from the remote gateway being restarted.
        """
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001 - closing must never mask the original error
                _LOGGER.debug("Daikin Modbus error while closing", exc_info=True)
            self._client = None

    async def _async_connect(self):
        """Connect modbus client."""
        if self._client is None:
            self._client = self._client_factory()
        if self._client.connected:
            return

        host = self._client.comm_params.host
        port = self._client.comm_params.port
        try:
            result = await self._client.connect()
        except (ModbusException, OSError, asyncio.TimeoutError) as ex:
            self._discard_client()
            _LOGGER.debug("Daikin Modbus unable to connect to %s:%s", host, port)
            raise ConnectionError(
                f"Daikin Modbus unable to connect to {host}:{port}: {ex}"
            ) from ex

        if not result:
            self._discard_client()
            _LOGGER.debug("Daikin Modbus unable to connect to %s:%s", host, port)
            raise ConnectionError(f"Daikin Modbus unable to connect to {host}:{port}")

        _LOGGER.debug("Daikin Modbus connected to %s:%s", host, port)

    async def async_close(self):
        """Disconnect modbus client."""
        async with self._lock:
            if self._client is not None:
                try:
                    self._client.close()
                except (ModbusException, OSError) as ex:
                    # Closing runs in a finally block, so a failure here must
                    # never replace the error that caused the close.
                    _LOGGER.debug("Daikin Modbus error while closing: %s", ex)
                    self._client = None

    async def async_disconnect(self):
        """Force the connection closed and discard the client.

        Used when an operation was cancelled part way through, which leaves the
        client's transaction state unknown and the connection untrustworthy.
        """
        async with self._lock:
            self._discard_client()

    async def async_setup(self):
        """Return a bool array of connected units."""
        async with self._lock:
            try:
                async with asyncio.timeout(SETUP_TIMEOUT):
                    await self._async_setup()
            except TimeoutError as ex:
                self._discard_client()
                raise ConnectionError(
                    f"Daikin Modbus discovery timed out after {SETUP_TIMEOUT} seconds"
                ) from ex

    async def _async_setup(self):
        """Discover units. Must already hold the lock."""
        await self._async_connect()
        if not self._units:
            self._units = []
            system_decoder: SystemStatus = await self._async_read(SystemStatus)
            _LOGGER.debug(
                "System Initialised: %s, Other Devices Exist: %s",
                system_decoder.initialised,
                system_decoder.other_device_exists,
            )

            for index, connected in enumerate(system_decoder.units_connected):
                if connected and not system_decoder.units_error[index]:
                    capabilities: UnitCapability = await self._async_read(
                        UnitCapability, index
                    )
                    status: UnitStatus = await self._async_read(UnitStatus, index)
                    unit = D3netUnit(self, index, capabilities, status)
                    self._units.append(unit)

            _LOGGER.info(
                "Discovered %s units",
                len(self._units),
            )

    async def async_read(self, Decoder: type[InputBase], index: int = 0) -> InputBase:
        """Load registers and return a decode object."""
        async with self._lock:
            await self._async_connect()
            return await self._async_read(Decoder, index)

    async def _async_read(self, Decoder: type[InputBase], index: int = 0) -> InputBase:
        """Load registers and return a decode object. Must already hold a lock and connection."""
        await self._throttle_start()
        address = Decoder.ADDRESS + index * Decoder.COUNT
        try:
            if Decoder.TYPE == D3netRegisterType.Holding:
                response = await self._client.read_holding_registers(
                    address=address,
                    count=Decoder.COUNT,
                    device_id=self._device_id,
                )
            else:
                response = await self._client.read_input_registers(
                    address=address,
                    count=Decoder.COUNT,
                    device_id=self._device_id,
                )
        except (ModbusException, OSError, asyncio.TimeoutError) as ex:
            self._discard_client()
            raise ConnectionError(
                f"Daikin Modbus read of address {address} failed: {ex}"
            ) from ex

        if response.isError():
            self._discard_client()
            raise ConnectionError(
                f"Daikin Modbus read of address {address} returned an error: {response}"
            )

        decoder = Decoder(response.registers)
        _LOGGER.debug(
            "Read %02i %s",
            index,
            decoder,
        )
        await self._throttle_end()
        return decoder

    async def async_write(self, decode: HoldingBase, index: int):
        """Write a register."""
        _LOGGER.debug(
            "%s %02i %s", ("Write" if decode.dirty else "Skipped write"), index, decode
        )
        if decode.dirty:
            async with self._lock:
                await self._async_connect()
                await self._throttle_start()
                address = decode.ADDRESS + index * decode.COUNT
                try:
                    response = await self._client.write_registers(
                        address=address,
                        device_id=self._device_id,
                        values=decode.registers,
                    )
                except (ModbusException, OSError, asyncio.TimeoutError) as ex:
                    self._discard_client()
                    raise ConnectionError(
                        f"Daikin Modbus write of address {address} failed: {ex}"
                    ) from ex

                if response.isError():
                    self._discard_client()
                    raise ConnectionError(
                        f"Daikin Modbus write of address {address} returned an error: {response}"
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
    ]

    def __init__(
        self,
        gateway: D3netGateway,
        index: int,
        capabilities: UnitCapability,
        status: UnitStatus,
    ) -> None:
        """Unit Initialize"""
        self._gateway = gateway
        self._index = index
        self._capabilities: UnitCapability = capabilities
        self._status: UnitStatus = status
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

    def filter_reset(self):
        """Reset the filter status."""
        self._holding.filter_reset = True

    async def async_update_status(self):
        """Load unit status."""
        # Don't update status if we've just written
        if self._holding is None or not self._holding.writeWithin(CACHE_WRITE):
            self._status = await self._gateway.async_read(UnitStatus, self._index)
        else:
            _LOGGER.debug(
                "Read %02i skipped on read-after-write delay",
                self._index,
            )

    async def async_write_prepare(self):
        """Prepare the holding registers for a write by reading them and making sure they match the current status."""
        # Only reload holding if it's not dirty and older than CACHE_WRITE, otherwise assume we're authorative.
        if self._holding is None or (
            not self._holding.dirty
            and not self._holding.readWithin(CACHE_WRITE)
            and not self._holding.writeWithin(CACHE_WRITE)
        ):
            self._holding = await self._gateway.async_read(UnitHolding, self._index)
            self._holding.sync(self._status, self.SYNC_PROPERTIES)
            if self._holding.dirty:
                # The holding registers are out of sync with status, so update them before making changes.
                # This is the whole point of doing a Prepare.
                _LOGGER.debug(
                    "Holding %02i out of sync with status, performing sync write",
                    self._index,
                )
                await self._gateway.async_write(self._holding, self._index)
        else:
            _LOGGER.debug(
                "Prepare %02i skipped on read-after-write delay",
                self._index,
            )

    async def async_write_commit(self):
        """Write any dirty holding registers."""
        # Copy the updated status registers into the holding registers
        self._holding.sync(self._status, self.SYNC_PROPERTIES)
        # They'll only write if there was something made dirty
        await self._gateway.async_write(self._holding, self._index)

        # If we're resetting the filter, we need to clear the reset and write it again
        if self._holding.filter_reset:
            self._holding.filter_reset = False
            await self._gateway.async_write(self._holding, self._index)
