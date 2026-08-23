"""Protocol-level tests for DIII-NET register decoding (no Home Assistant)."""

from __future__ import annotations

import sys
from pathlib import Path

# Import the protocol package directly so Home Assistant / pymodbus are not required.
ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "daikin_d3net"
sys.path.insert(0, str(ROOT))

from d3net.const import (  # noqa: E402
    D3netCoolHeatMaster,
    D3netOperationMode,
    D3netVentilationMode,
)
from d3net.encoding import (  # noqa: E402
    UnitError,
    UnitStatus,
    UnitVentilation,
    UnitVentilationHolding,
)
from d3net.error_codes import lookup_error_message  # noqa: E402


def test_signed_temperature_roundtrip():
    status = UnitStatus([0, 0, 220, 0, 0x8000 | 55, 0])  # -5.5°C current, 22.0 setpoint
    assert status.temp_setpoint == 22.0
    assert status.temp_current == -5.5
    status.temp_setpoint = -3.5
    assert status.temp_setpoint == -3.5


def test_forced_off_is_bit2():
    status = UnitStatus([0x4, 0, 0, 0, 0, 0])
    assert status.forced_off is True
    assert status.power is False


def test_cool_heat_master_and_vent_mode():
    # register 1: mode=VENT(4) in bits 3-0, master=2 in bits 15-14
    status = UnitStatus([0, (2 << 14) | 4, 0, 0, 0, 0])
    assert status.operating_mode == D3netOperationMode.VENT
    assert status.cool_heat_master == D3netCoolHeatMaster.MASTER


def test_error_code_ascii_order():
    # 33601: high char 'C' in bits 15-8, low char '7' in bits 7-0 -> "C7"
    higher = ord("C")
    lower = ord("7")
    error = UnitError([(higher << 8) | lower, 0x0100])  # error bit 8 of 2nd register = bit 24
    assert error.error_code == "C7"
    assert error.error_code_present is True
    assert error.error is True
    assert lookup_error_message("C7") is not None


def test_error_code_idle_is_00():
    error = UnitError([(ord("0") << 8) | ord("0"), 0])
    assert error.error_code == "00"
    assert error.error_code_present is False
    assert lookup_error_message("00") is None
    assert lookup_error_message("U4") == "室內機BS設備和室外機之間傳送故障"


def test_ventilation_mode_bits():
    # 32804 is the 4th register; bits 7-6 = 2 (energy reclaim)
    registers = [0, 0, 0, 2 << 6]
    vent = UnitVentilation(registers)
    assert vent.ventilation_mode == D3netVentilationMode.ENERGY_RECLAIM

    holding = UnitVentilationHolding(list(registers))
    holding.load_from_input(vent)
    assert holding.dirty is False
    holding.ventilation_mode = D3netVentilationMode.BYPASS
    assert holding.dirty is True
    assert holding.ventilation_mode == D3netVentilationMode.BYPASS
    assert (holding.registers[3] >> 6) & 0x3 == 3


if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("ok", _name)
    print("all passed")
