"""Signed register fields (DTA116A51 spec CB13A033 section 5).

Every signed field is two's complement with its sign in the field's top bit:
8 bit setpoint limits (-128 to 127 degC), and 16 bit setpoint and room
temperature in 0.1 degC steps.
"""

import pytest

from conftest import regs
from d3net.encoding import UnitCapability, UnitHolding, UnitStatus

# Real registers from a unit cooling at 24.0 degC with the room at 23.2 degC.
STATUS = (
    "0001000000000001 0100001000010010 0000000011110000 "
    "0000000000000000 0000000011101000 1000000000000000"
)
HOLDING = "0001000001100001 0000001000000010 0000000011110000"


def test_decodes_real_registers():
    status = UnitStatus(regs(STATUS))
    assert status.temp_setpoint == 24.0
    assert status.temp_current == 23.2
    assert UnitHolding(regs(HOLDING)).temp_setpoint == 24.0


def test_status_setpoint_ignores_error_code_register():
    # Register 3 holds the error code. Its lowest bit used to be read as the
    # setpoint's sign, turning 24.0 into -24.0.
    registers = regs(STATUS)
    registers[3] = 0b1
    assert UnitStatus(registers).temp_setpoint == 24.0


def test_room_temperature_ignores_next_register():
    registers = regs(STATUS)
    registers[5] |= 0b1
    assert UnitStatus(registers).temp_current == 23.2


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0x00F0, 24.0),
        (0x00E1, 22.5),
        (0xFFCE, -5.0),
        (0xFFFF, -0.1),
        (0x04FF, 127.9),
        (0xFB01, -127.9),
    ],
)
def test_decodes_16_bit_twos_complement(raw, expected):
    registers = regs(STATUS)
    registers[2] = raw
    registers[4] = raw
    status = UnitStatus(registers)
    assert status.temp_setpoint == expected
    assert status.temp_current == expected


@pytest.mark.parametrize(
    ("setpoint", "raw"),
    [(24.0, 0x00F0), (22.5, 0x00E1), (-5.0, 0xFFCE), (127.9, 0x04FF), (-127.9, 0xFB01)],
)
def test_encodes_16_bit_twos_complement(setpoint, raw):
    holding = UnitHolding(regs(HOLDING))
    holding.temp_setpoint = setpoint
    assert holding.registers[2] == raw
    assert holding.temp_setpoint == setpoint
    # The other registers are untouched.
    assert holding.registers[:2] == regs(HOLDING)[:2]


def test_encoding_the_same_setpoint_is_not_a_change():
    holding = UnitHolding(regs(HOLDING))
    holding.temp_setpoint = 24.0
    assert not holding.dirty
    holding.temp_setpoint = 24.5
    assert holding.dirty


def _capability(cool_upper, cool_lower, heat_upper, heat_lower):
    byte = lambda value: value & 0xFF
    return UnitCapability(
        [
            0,
            byte(cool_upper) | byte(cool_lower) << 8,
            byte(heat_upper) | byte(heat_lower) << 8,
        ]
    )


def test_decodes_setpoint_limits():
    capability = _capability(32, 16, 32, 16)
    assert capability.cool_setpoint_upperlimit == 32
    assert capability.cool_setpoint_lowerlimit == 16
    assert capability.heat_setpoint_upperlimit == 32
    assert capability.heat_setpoint_lowerlimit == 16


def test_setpoint_limits_ignore_neighbouring_odd_limits():
    # Each limit used to take its sign from the next limit's lowest bit.
    capability = _capability(32, 17, 31, 15)
    assert capability.cool_setpoint_upperlimit == 32
    assert capability.cool_setpoint_lowerlimit == 17
    assert capability.heat_setpoint_upperlimit == 31
    assert capability.heat_setpoint_lowerlimit == 15


def test_decodes_negative_setpoint_limits():
    capability = _capability(127, -128, -1, -40)
    assert capability.cool_setpoint_upperlimit == 127
    assert capability.cool_setpoint_lowerlimit == -128
    assert capability.heat_setpoint_upperlimit == -1
    assert capability.heat_setpoint_lowerlimit == -40


def test_reading_past_the_registers_raises_value_error():
    holding = UnitHolding(regs(HOLDING))
    with pytest.raises(ValueError, match="outside of register buffer"):
        holding._bit(3 * 16)
