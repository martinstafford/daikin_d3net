"""Daikin DIII-Net Modbus data structures."""

import logging

from .const import (
    D3netFanDirection,
    D3netFanSpeed,
    D3netFanSpeedCapability,
    D3netOperationMode,
)

_LOGGER = logging.getLogger(__name__)


class EncodingBase:
    """Base class of data structues."""

    ADDRESS = None
    COUNT = None

    def __init__(self, unit, registers: list[int]) -> None:
        """Initialize the base object."""
        self._registers = registers
        self._unit = unit
        self._dirty = False

    @property
    def registers(self) -> list[int]:
        return self._registers

    @property
    def unit(self):
        return self._unit

    @property
    def dirty(self) -> bool:
        """Return the dirty state of the object."""
        return self._dirty

    @dirty.setter
    def dirty(self, state: bool):
        """Set the dirty state of the object."""
        self._dirty = state

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

    def _zero(self, start: int, length: int) -> int:
        """Zeros bits in the register array."""
        for bit in range(start, start + length):
            if self._register[int(bit / 16)] & 1 << bit % 16:
                self._register[int(bit / 16)] -= 1 << bit % 16

    def _encode_bit(self, start: int, value: bool):
        """Encode a bit into a position in a register."""
        self._zero(start, 1)
        if value:
            self._register[int(start / 16)] += 1 << start % 16

    def _encode_uint(self, start: int, length: int, value: int):
        self._zero(start, length)
        for bit in range(length):
            if value & 1 << bit:
                self._register[int(start / 16)] += 1 << (start + bit) % 16

    def _encode_sint(self, start: int, length: int, value: int):
        self._zero(start, length)
        self._encode_uint(start, length - 1, abs(value))
        self._encode_bit(start + length - 1, value < 0)


class DecodeSystemStatus(EncodingBase):
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


class DecodeUnitCapability(EncodingBase):
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


class DecodeUnitStatus(EncodingBase):
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

    @power.setter
    def power(self, state: bool):
        """Set the power state of the unit."""
        self._encode_bit(0, state)
        self._dirty = True

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
        self._dirty = True

    @property
    def fan_speed(self) -> D3netFanSpeed:
        """Fan Speed."""
        return D3netFanSpeed(self._decode_uint(12, 3))

    @fan_speed.setter
    def fan_speed(self, speed: D3netFanSpeed):
        """Set the fan speed."""
        self._encode_uint(12, 3, speed.value)
        self._dirty = True

    @property
    def operating_mode(self):
        """Operation mode setting."""
        return D3netOperationMode(self._decode_uint(16, 4))

    @operating_mode.setter
    def operating_mode(self, mode: D3netOperationMode):
        """Set the operating mode"""
        self._encode_uint(16, 4, mode.value)
        self._dirty = True

    @property
    def filter_warning(self) -> bool:
        """Operation mode setting."""
        return self._decode_uint(20, 4) != 0

    @filter_warning.setter
    def filter_warning(self, state: bool):
        """Reset the filter status."""
        self._encode_uint(20, 4, 15 if state else 0)
        self._dirty = True

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
        self._encode_sint(32, 16, int(setpoint * 10))
        self._dirty = True

    @property
    def temp_current(self) -> float:
        """Temperature Set Point."""
        return self._decode_sint(64, 16) / 10


class DecodeUnitError(EncodingBase):
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


class DecodeHolding(EncodingBase):
    """Decode the holding registers."""

    ADDRESS = 2000
    COUNT = 3

    SYNC_PROPERTIES = [
        "power",
        "fan_direct",
        "fan_speed",
        "operating_mode",
        "temp_setpoint",
        "filter_warning",
    ]

    def __init__(self, unit, registers: list[int]) -> None:
        """Initialize the writer."""
        self._unit = unit
        super().__init__(registers)

        # Copy in any statuses from the unit status
        for property in self.SYNC_PROPERTIES:
            if getattr(self, property) != getattr(unit.status, property):
                setattr(self, property, getattr(unit.status, property))

    @property
    def power(self) -> bool:
        """The power state of the unit."""
        return self._decode_bit(0)

    @power.setter
    def power(self, state: bool):
        """Set the power state of the unit."""
        self._encode_bit(0, state)
        self._dirty = True
        self.unit.status.power = state

    @property
    def fan_direct(self) -> D3netFanDirection:
        """Fan Direction."""
        return D3netFanDirection(self._decode_uint(8, 3))

    @fan_direct.setter
    def fan_direct(self, direct: D3netFanDirection):
        """Set the fan direction."""
        self._encode_uint(8, 3, direct.value)
        self._dirty = True
        self.unit.status.fan_direct = direct

    @property
    def fan_speed(self) -> D3netFanSpeed:
        """Fan Speed."""
        return D3netFanSpeed(self._decode_uint(12, 3))

    @fan_speed.setter
    def fan_speed(self, speed: D3netFanSpeed):
        """Set the fan speed."""
        self._encode_uint(12, 3, speed.value)
        self._dirty = True
        self.unit.status.fan_speed = speed

    @property
    def operating_mode(self):
        """Operation mode setting."""
        return D3netOperationMode(self._decode_uint(16, 4))

    @operating_mode.setter
    def operating_mode(self, mode: D3netOperationMode):
        """Set the operating mode"""
        self._encode_uint(16, 4, mode.value)
        self._dirty = True
        self.unit.status.operating_mode = mode

    @property
    def temp_setpoint(self) -> float:
        """Temperature Set Point."""
        return self._decode_sint(32, 16) / 10

    @temp_setpoint.setter
    def temp_setpoint(self, setpoint: float):
        self._encode_sint(32, 16, int(setpoint * 10))
        self._dirty = True
        self.unit.status.temp_setpoint = setpoint

    @property
    def filter_warning(self) -> bool:
        """Operation mode setting."""
        return self._decode_uint(20, 4) != 0

    @filter_warning.setter
    def filter_warning(self, state: bool):
        """Reset the filter status."""
        self._encode_uint(20, 4, 15 if state else 0)
        self._dirty = True
        self.unit.status.filter_warning = state
