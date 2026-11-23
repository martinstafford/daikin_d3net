"""Shared test setup.

The d3net package only depends on pymodbus, not Home Assistant, so the tests
import it directly from custom_components/daikin_d3net.
"""

import pathlib
import sys
import time

import pytest

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "daikin_d3net")
)


def regs(text: str) -> list[int]:
    """Parse register dumps in the integration's debug-log format (MSB first)."""
    return [int(word, 2) for word in text.split()]


class _Response:
    def __init__(self, registers=None, error=False):
        self.registers = registers
        self._error = error

    def isError(self):
        return self._error


class FakeModbusClient:
    """Minimal stand-in for a pymodbus client talking to a DTA116A51.

    Keeps separate input and holding register maps, and records every write
    with its perf_counter() time.
    """

    class comm_params:
        host = "fake"
        port = 0

    def __init__(self):
        self.connected = True
        self.input: dict[int, int] = {}
        self.holding: dict[int, int] = {}
        self.writes: list[tuple[float, int, list[int]]] = []
        self.holding_reads: list[int] = []
        self.fail_writes = False

    async def connect(self):
        self.connected = True
        return True

    def close(self):
        pass

    def set_input(self, address: int, values: list[int]):
        for offset, value in enumerate(values):
            self.input[address + offset] = value

    def set_holding(self, address: int, values: list[int]):
        for offset, value in enumerate(values):
            self.holding[address + offset] = value

    async def read_input_registers(self, address, count, device_id):
        return _Response([self.input.get(address + i, 0) for i in range(count)])

    async def read_holding_registers(self, address, count, device_id):
        self.holding_reads.append(address)
        return _Response([self.holding.get(address + i, 0) for i in range(count)])

    async def write_registers(self, address, device_id, values):
        if self.fail_writes:
            raise OSError("simulated write failure")
        self.writes.append((time.perf_counter(), address, list(values)))
        self.set_holding(address, values)
        return _Response()


@pytest.fixture
def fake_client():
    return FakeModbusClient()
