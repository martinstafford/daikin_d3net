"""Daikin DIII-Net Modbus data structures."""

from enum import Enum
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)


class D3netOperationMode(Enum):
    """Unit Operating Modes."""

    FAN = 0
    HEAT = 1
    COOL = 2
    AUTO = 3
    VENT = 4
    UNDEFINED = 5
    SLAVE = 6
    DRY = 7


class D3netFanSpeedCapability(Enum):
    """Unit Fan Speed Capability."""

    Fixed = 1
    Step2 = 2
    Step3 = 3
    Step4 = 4
    Step5 = 5


class D3netFanSpeed(Enum):
    """Unit Fan Speed."""

    Auto = 0
    Low = 1
    LowMedium = 2
    Medium = 3
    HighMedium = 4
    High = 5


class D3netFanDirection(Enum):
    """Unit Fan Direction."""

    P0 = 0
    P1 = 1
    P2 = 2
    P3 = 3
    P4 = 4
    Stop = 6
    Swing = 7


class DecodeBase:
    """Base class of data structues."""

    ADDRESS = None
    COUNT = None

    def __init__(self, registers) -> None:
        """Initialize the base object."""
        self._registers = registers

    def _decode_bit_array(self, start, length):
        """Decode a word into an array of bits."""
        if start + length > self.COUNT * 16:
            raise ValueError("Reading outside of register buffer")
        return [
            (self._registers[int(x / 16)] & (1 << x % 16) > 0)
            for x in range(start, start + length)
        ]

    def _decode_bit(self, start) -> bool:
        """Decode an int from the registers."""
        if start > self.COUNT * 16:
            raise ValueError("Reading outside of register buffer")

        return self._registers[int(start / 16)] & (1 << (start % 16)) > 0

    def _decode_uint(self, start, length) -> int:
        """Decode an int from the registers."""
        if length > 64:
            raise ValueError("Maximum decode length exceeded")
        if start + length > self.COUNT * 16:
            raise ValueError("Reading outside of register buffer")

        result: int = 0
        for bit in range(length):
            if self._registers[int((start + bit) / 16)] & (1 << ((start + bit) % 16)):
                result += 1 << bit
        return result

    def _decode_sint(self, start, length) -> int:
        result = self._decode_uint(start, length - 1)
        if self._decode_bit(start + length):
            result = 0 - result
        return result


class DecodeSystemStatus(DecodeBase):
    """Decode System Status."""

    ADDRESS = 0
    COUNT = 9

    def __init__(self, registers) -> None:
        """Decode unit capability."""
        super().__init__(registers)

    @property
    def initialised(self) -> bool:
        """Is the interface initialised and communciating."""
        return self._decode_bit(0)

    @property
    def connected(self) -> bool:
        """Is the interface connected to other devices."""
        return self._decode_bit(1)

    @property
    def units_connected(self):
        """Is the interface connected to other devices."""
        return self._decode_bit_array(16, 64)

    @property
    def units_error(self):
        """Is the interface connected to other devices."""
        return self._decode_bit_array(80, 64)


class DecodeUnitCapability(DecodeBase):
    """Decode Unit Capabilities."""

    ADDRESS = 1000
    COUNT = 3

    def __init__(self, registers) -> None:
        """Decode unit capability."""
        super().__init__(registers)

    @property
    def fan_mode_capable(self) -> bool:
        """Is the unit capable of FAN mode."""
        return self._decode_bit(0)

    @property
    def cool_mode_capable(self) -> bool:
        """Is the unit capable of COOL mode."""
        return self._decode_bit(1)

    @property
    def heat_mode_capable(self) -> bool:
        """Is the unit capable of HEAT mode."""
        return self._decode_bit(2)

    @property
    def auto_mode_capable(self) -> bool:
        """Is the unit capable of AUTO mode."""
        return self._decode_bit(3)

    @property
    def dry_mode_capable(self) -> bool:
        """Is the unit capable of DRY mode."""
        return self._decode_bit(4)

    @property
    def fan_direct_capable(self) -> bool:
        """Is the unit capable of FAN DIRECTION."""
        return self._decode_bit(11)

    @property
    def fan_direct_steps(self) -> int:
        """Enum of FAN DIRECTION STEPS."""
        return self._decode_uint(8, 3)

    @property
    def fan_speed_capable(self) -> bool:
        """Is the unit capable of FAN SPEED."""
        return self._decode_bit(15)

    @property
    def fan_speed_steps(self) -> D3netFanSpeedCapability:
        """Enum of FAN SPEED STEPS."""
        return D3netFanSpeedCapability(self._decode_uint(12, 3))

    @property
    def cool_setpoint_upperlimit(self) -> int:
        """Upper Limit of COOL temperature setpoint."""
        return self._decode_sint(16, 8)

    @property
    def cool_setpoint_lowerlimit(self) -> int:
        """Lower Limit of COOL temperature setpoint."""
        return self._decode_sint(24, 8)

    @property
    def heat_setpoint_upperlimit(self) -> int:
        """Upper Limit of HEAT temperature setpoint."""
        return self._decode_sint(32, 8)

    @property
    def heat_setpoint_lowerlimit(self) -> int:
        """Lower Limit of Heat temperature setpoint."""
        return self._decode_sint(40, 8)


class DecodeUnitStatus(DecodeBase):
    """Decode Unit Status."""

    ADDRESS = 2000
    COUNT = 6

    def __init__(self, registers) -> None:
        """Decode unit status."""
        super().__init__(registers)

    @property
    def power(self) -> bool:
        """The power state of the unit."""
        return self._decode_bit(0)

    @property
    def forced_off(self) -> bool:
        """Has the unit been forced off."""
        return self._decode_bit(2)

    @property
    def normal_operation(self) -> bool:
        """Is the unit operating normally."""
        return self._decode_bit(3)

    @property
    def fan(self) -> bool:
        """Fan Status."""
        return self._decode_bit(5)

    @property
    def heat(self) -> bool:
        """Heat Status."""
        return self._decode_bit(6)

    @property
    def thermo(self) -> bool:
        """Thermo Status."""
        return self._decode_bit(7)

    @property
    def fan_direct(self) -> D3netFanDirection:
        """Fan Direction."""
        return D3netFanDirection(self._decode_uint(8, 3))

    @property
    def fan_speed(self) -> D3netFanSpeed:
        """Fan Speed."""
        return D3netFanSpeed(self._decode_uint(12, 3))

    @property
    def operating_mode(self):
        """Operation mode setting."""
        return D3netOperationMode(self._decode_uint(16, 4))

    @property
    def filter_warning(self) -> bool:
        """Operation mode setting."""
        return self._decode_uint(20, 4) != 0

    @property
    def operating_current(self) -> D3netOperationMode:
        """Operation mode setting."""
        return D3netOperationMode(self._decode_uint(24, 4))

    @property
    def defrost(self) -> bool:
        """Heat Status."""
        return self._decode_bit(29)

    @property
    def temp_setpoint(self) -> float:
        """Temperature Set Point."""
        return self._decode_sint(32, 16) / 10

    @property
    def temp_current(self) -> float:
        """Temperature Set Point."""
        return self._decode_sint(64, 16) / 10


class DecodeUnitError(DecodeBase):
    """Decode Unit Errors."""

    ADDRESS = 3600
    COUNT = 2

    def __init__(self, registers) -> None:
        """Decode unit Errors."""
        super().__init__(registers)

    @property
    def error_code(self) -> str:
        """Unit Error Code."""
        return chr(self._decode_uint(0, 8)) + chr(self._decode_uint(8, 8))

    @property
    def error_sub_code(self) -> int:
        """Unit Error Sub Code."""
        return self._decode_uint(16, 6)

    @property
    def error(self) -> int:
        """Unit Error State."""
        return self._decode_bit(24)

    @property
    def alarm(self) -> int:
        """Unit Alarm State."""
        return self._decode_bit(25)

    @property
    def warning(self) -> int:
        """Unit Warning State."""
        return self._decode_bit(26)

    @property
    def error_unit_number(self) -> int:
        """Error Unit Number if different units are connected to the same DIII group address."""
        return self._decode_uint(28, 4)


class Writer:
    """Write registers."""

    def __init__(self, unit) -> None:
        """Initialize the writer."""
        self._unit = unit

    def _encode_bit(self, register: int, start: int, value: bool):
        """Encode a bit into a position in a register."""
        if value:
            register += 1 << start
        return register

    def _encode_uint(self, register: int, start: int, length: int, value: int):
        for bit in range(length):
            if value & 1 << bit:
                register += 1 << start + bit
        return register

    def _encode_sint(self, register: int, start: int, length: int, value: int):
        register = self._encode_uint(register, start, length - 1, abs(value))
        return self._encode_bit(register, length - 1, value < 0)

    async def write(
        self,
        power: bool | None = None,
        fan_speed: D3netFanSpeed = None,
        fan_direct: D3netFanDirection = None,
        operating_mode: D3netOperationMode = None,
        temp_setpoint: float | None = None,
        filter_reset: bool | None = None,
    ):
        """Read status, set holding registers then write updates to unit."""
        # Read the current status into decoder
        await self._unit.gateway.async_unit_status(self._unit)
        # Write the current status to the holding registers
        await self._write()
        # Sleep for 0.5 seconds before writing to the holding registers again
        await asyncio.sleep(0.5)
        # Write the passed values to the holding registers
        await self._write(
            power=power,
            fan_speed=fan_speed,
            fan_direct=fan_direct,
            operating_mode=operating_mode,
            filter_reset=filter_reset,
            temp_setpoint=temp_setpoint,
        )
        # Sleep to wait for the unit to change status and report back to gateway
        await asyncio.sleep(3)
        # Read in the updated status to the decoder
        await self._unit.gateway.async_unit_status(self._unit)

    async def _write(
        self,
        power: bool | None = None,
        fan_speed: D3netFanSpeed = None,
        fan_direct: D3netFanDirection = None,
        operating_mode: D3netOperationMode = None,
        filter_reset: bool | None = None,
        temp_setpoint: float | None = None,
    ):
        """Write holding registers to unit. Use supplied values or fall back to current status."""

        # Power and fan details in register 0
        register0 = 0
        register0 = self._encode_bit(
            register0, 0, self._unit.status.power if power is None else power
        )
        register0 = self._encode_uint(
            register0, 4, 4, 6 if self._unit.capabilities.fan_speed_capable else 0
        )
        register0 = self._encode_uint(
            register0,
            8,
            3,
            self._unit.status.fan_direct.value
            if fan_direct is None
            else fan_direct.value,
        )
        register0 = self._encode_uint(
            register0,
            12,
            3,
            self._unit.status.fan_speed.value if fan_speed is None else fan_speed.value,
        )

        # Operating mode in register 1
        register1 = 0
        register1 = self._encode_uint(
            register1,
            0,
            3,
            self._unit.status.operating_mode.value
            if operating_mode is None
            else operating_mode.value,
        )
        register1 = self._encode_uint(register1, 4, 4, 15 if filter_reset else 0)

        # Setpoint temperature in register 2
        register2 = 0
        register2 = self._encode_sint(
            register2,
            0,
            16,
            int(
                (
                    self._unit.status.temp_setpoint
                    if temp_setpoint is None
                    else temp_setpoint
                )
                * 10
            ),
        )
        await self._unit.gateway.async_write(
            2000 + self._unit.index * 3, [register0, register1, register2]
        )
