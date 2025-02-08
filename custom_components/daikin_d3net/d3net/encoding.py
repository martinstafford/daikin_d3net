"""Daikin DIII-Net Modbus data structures."""

import logging
import time

from .const import (
    D3netFanDirection,
    D3netFanSpeed,
    D3netFanSpeedCapability,
    D3netOperationMode,
    D3netRegisterType,
)

_LOGGER = logging.getLogger(__name__)


class InputBase:
    """Base class of data structues."""

    ADDRESS = None
    COUNT = None
    TYPE = D3netRegisterType.Input

    def __init__(self, registers: list[int]) -> None:
        """Initialize the base object."""

        if self.ADDRESS is None:
            raise ValueError("Modbus address not set")
        if self.COUNT != len(registers):
            raise ValueError(
                "Register array length (%s) difference from object expection (%s)"
                % (len(registers), self.COUNT)
            )

        self._registers = registers
        self._dirty = False
        self._timeRead = time.perf_counter()

    def _bit(self, bit: int, value: bool | None = None):
        """Base bit manipulation of the register array"""
        register = int(bit / 16)
        mask = 1 << (bit % 16)

        if self.COUNT is None:
            raise ValueError("Object register count not set")
        if register > self.COUNT:
            raise ValueError("Reading outside of register buffer")

        current = self._registers[register] & mask > 0
        if value is None or value == current:
            return current

        self._registers[register] += mask * (1 if value else -1)
        self._dirty = True
        return value

    def _decode_bit_array(self, start, length):
        """Decode a word into an array of bits."""
        return [self._bit(x) for x in range(start, start + length)]

    def _decode_bit(self, start) -> bool:
        """Decode a bit from the registers."""
        return self._bit(start)

    def _decode_uint(self, start, length) -> int:
        """Decode an unsigned int from the registers."""
        result: int = 0
        for bit in range(length):
            if self._bit(start + bit):
                result += 1 << bit
        return result

    def _decode_sint(self, start, length) -> int:
        """Decode a signed int from the registers."""
        result = self._decode_uint(start, length - 1)
        if self._bit(start + length):
            result = 0 - result
        return result

    def _encode_bit(self, start: int, value: bool):
        """Encode a bit into a position in a register."""
        self._bit(start, value)

    def _encode_uint(self, start: int, length: int, value: int):
        """Encode an unsigned int into a position in a register."""
        for bit in range(length):
            self._bit(start + bit, (value & 1 << bit) > 0)

    def _encode_sint(self, start: int, length: int, value: int):
        """Encode a signed int into a position in a register."""
        self._encode_uint(start, length - 1, abs(value))
        self._encode_bit(start + length - 1, value < 0)

    def readWithin(self, seconds: float):
        """Whether the registers have been loaded from modbus withing X seconds."""
        return time.perf_counter() - self._timeRead < seconds

    def __str__(self):
        """Return class name and register contents."""
        registers = ""
        for register in self._registers:
            registers += "{0:016b} ".format(register)
        return type(self).__name__ + " [ " + str(registers) + "]"


class HoldingBase(InputBase):
    """Base class for Holding Registers."""

    TYPE = D3netRegisterType.Holding

    def __init__(self, registers) -> None:
        """Specific init for Holding registers."""
        super().__init__(registers)
        self._timeWrite = None

    @property
    def dirty(self) -> bool:
        """Return the dirty state of the object."""
        return self._dirty

    @property
    def registers(self) -> list[int]:
        """Internal register array."""
        return self._registers

    def sync(self, source, properties: list[str]):
        """Copy properties in from another object."""
        for prop in properties:
            setattr(self, prop, getattr(source, prop))

    def writeWithin(self, seconds: float):
        """Was the object written to modbus within the last X mins."""
        if self._timeWrite is None:
            return False
        return time.perf_counter() - self._timeWrite < seconds

    def written(self):
        """Update the object status to reflect that it has just been written."""
        self._timeWrite = time.perf_counter()
        self._dirty = False


class SystemStatus(InputBase):
    """Decode System Status."""

    ADDRESS = 0
    COUNT = 9

    @property
    def initialised(self) -> bool:
        """Is the interface initialised and communciating."""
        return self._decode_bit(0)

    @property
    def other_device_exists(self) -> bool:
        """Are other devices connected to DIII net."""
        return self._decode_bit(1)

    @property
    def units_connected(self):
        """Is the interface connected to other devices."""
        return self._decode_bit_array(16, 64)

    @property
    def units_error(self):
        """Is the interface connected to other devices."""
        return self._decode_bit_array(80, 64)


class UnitCapability(InputBase):
    """Decode Unit Capabilities."""

    ADDRESS = 1000
    COUNT = 3

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


class UnitStatus(InputBase):
    """Decode Unit Status."""

    ADDRESS = 2000
    COUNT = 6

    @property
    def power(self) -> bool:
        """The power state of the unit."""
        return self._decode_bit(0)

    @power.setter
    def power(self, state: bool):
        """Set the power state of the unit."""
        self._encode_bit(0, state)

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

    @fan_direct.setter
    def fan_direct(self, direct: D3netFanDirection):
        """Set the fan direction."""
        self._encode_uint(8, 3, direct.value)

    @property
    def fan_speed(self) -> D3netFanSpeed:
        """Fan Speed."""
        return D3netFanSpeed(self._decode_uint(12, 3))

    @fan_speed.setter
    def fan_speed(self, speed: D3netFanSpeed):
        """Set the fan speed."""
        self._encode_uint(12, 3, speed.value)

    @property
    def operating_mode(self):
        """Operation mode setting."""
        return D3netOperationMode(self._decode_uint(16, 4))

    @operating_mode.setter
    def operating_mode(self, mode: D3netOperationMode):
        """Set the operating mode"""
        self._encode_uint(16, 4, mode.value)

    @property
    def filter_warning(self) -> bool:
        """Filter sign status."""
        return self._decode_uint(20, 4) != 0

    @filter_warning.setter
    def filter_warning(self, state: bool):
        """Reset the filter status."""
        self._encode_uint(20, 4, 15 if state else 0)

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

    @temp_setpoint.setter
    def temp_setpoint(self, setpoint: float):
        """Set the setpoint temperature"""
        self._encode_sint(32, 16, int(setpoint * 10))

    @property
    def temp_current(self) -> float:
        """Temperature Set Point."""
        return self._decode_sint(64, 16) / 10


class UnitError(InputBase):
    """Decode Unit Errors."""

    ADDRESS = 3600
    COUNT = 2

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


class UnitHolding(HoldingBase):
    """Decode the holding registers."""

    ADDRESS = 2000
    COUNT = 3

    @property
    def power(self) -> bool:
        """The power state of the unit."""
        return self._decode_bit(0)

    @power.setter
    def power(self, state: bool):
        """Set the power state of the unit."""
        self._encode_bit(0, state)

    @property
    def fan_direct(self) -> D3netFanDirection:
        """Fan Direction."""
        return D3netFanDirection(self._decode_uint(8, 3))

    @fan_direct.setter
    def fan_direct(self, direct: D3netFanDirection):
        """Set the fan direction."""
        self._encode_uint(8, 3, direct.value)
        self.fan_control = True

    @property
    def fan_speed(self) -> D3netFanSpeed:
        """Fan Speed."""
        return D3netFanSpeed(self._decode_uint(12, 3))

    @fan_speed.setter
    def fan_speed(self, speed: D3netFanSpeed):
        """Set the fan speed."""
        self._encode_uint(12, 3, speed.value)
        self.fan_control = True

    @property
    def fan_control(self) -> bool:
        """Status of fan control."""
        return self._decode_uint(4, 4) == 6

    @fan_control.setter
    def fan_control(self, enabled: bool):
        """Flag that fan control is enabled."""
        self._encode_uint(4, 4, 6 if enabled else 0)

    @property
    def operating_mode(self):
        """Operation mode setting."""
        return D3netOperationMode(self._decode_uint(16, 4))

    @operating_mode.setter
    def operating_mode(self, mode: D3netOperationMode):
        """Set the operating mode."""
        self._encode_uint(16, 4, mode.value)

    @property
    def temp_setpoint(self) -> float:
        """Temperature Set Point."""
        return self._decode_sint(32, 16) / 10

    @temp_setpoint.setter
    def temp_setpoint(self, setpoint: float):
        self._encode_sint(32, 16, int(setpoint * 10))

    @property
    def filter_reset(self) -> bool:
        """Operation mode setting."""
        return self._decode_uint(20, 4) != 0

    @filter_reset.setter
    def filter_reset(self, state: bool):
        """Reset the filter status."""
        self._encode_uint(20, 4, 15 if state else 0)
