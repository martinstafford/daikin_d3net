"""Minimum interval between writes to the same unit (CB13A033 p31).

The DTA116A51 only sends a command when a holding register value changes, and
writes to the same register must be at least 0.5 s apart. Writes closer
together than that can be missed.
"""

import asyncio
import time

import pytest

from conftest import regs
from d3net import gateway as gateway_module
from d3net.encoding import UnitCapability, UnitHolding, UnitStatus
from d3net.gateway import D3netGateway, D3netUnit

INTERVAL = 0.2  # shortened from 1 s to keep the tests quick
SLACK = 0.02  # timer jitter allowance

# Real registers: unit off at the wall controller, while the holding
# registers still hold the integration's last command (on).
STATUS_OFF = (
    "0001000000000000 0100001000010010 0000000011110000 "
    "0000000000000000 0000000011101000 1000000000000000"
)
HOLDING_ON = "0001000001100001 0000001000000010 0000000011110000"


@pytest.fixture(autouse=True)
def short_interval(monkeypatch):
    # raising=False so the tests still run (and fail) without the setting.
    monkeypatch.setattr(gateway_module, "WRITE_INTERVAL", INTERVAL, raising=False)


def _holding(power: bool) -> UnitHolding:
    """Holding registers with power just changed to `power`, so they get written."""
    holding = UnitHolding(regs(HOLDING_ON))
    holding.power = not power
    holding.written()
    holding.power = power
    return holding


def _gaps(writes):
    return [later[0] - earlier[0] for earlier, later in zip(writes, writes[1:])]


def test_writes_to_the_same_unit_are_spaced(fake_client):
    gateway = D3netGateway(lambda: fake_client, 1)

    async def run():
        await gateway.async_write(_holding(False), 0)
        await gateway.async_write(_holding(True), 0)

    asyncio.run(run())
    assert len(fake_client.writes) == 2
    assert _gaps(fake_client.writes)[0] >= INTERVAL - SLACK


def test_writes_to_other_units_are_not_delayed(fake_client):
    gateway = D3netGateway(lambda: fake_client, 1)

    async def run():
        await gateway.async_write(_holding(False), 0)
        await gateway.async_write(_holding(True), 1)

    asyncio.run(run())
    assert len(fake_client.writes) == 2
    assert _gaps(fake_client.writes)[0] < INTERVAL / 2


def test_write_after_the_interval_is_not_delayed(fake_client):
    gateway = D3netGateway(lambda: fake_client, 1)

    async def run():
        await gateway.async_write(_holding(False), 0)
        await asyncio.sleep(INTERVAL)
        start = time.perf_counter()
        await gateway.async_write(_holding(True), 0)
        return time.perf_counter() - start

    assert asyncio.run(run()) < INTERVAL / 2


def test_skipped_writes_are_not_delayed(fake_client):
    gateway = D3netGateway(lambda: fake_client, 1)
    unchanged = UnitHolding(regs(HOLDING_ON))  # not dirty, so not written

    async def run():
        await gateway.async_write(_holding(False), 0)
        start = time.perf_counter()
        await gateway.async_write(unchanged, 0)
        return time.perf_counter() - start

    assert asyncio.run(run()) < INTERVAL / 2
    assert len(fake_client.writes) == 1


def test_sync_write_and_command_are_spaced(fake_client):
    """The failure case from #16.

    HA turned the unit on, someone turned it off at the wall, and HA turns it
    on again. Prepare writes the status (off) into the stale holding registers,
    then commit writes on. Those two writes used to land ~80 ms apart.
    """
    fake_client.set_input(2000, regs(STATUS_OFF))
    fake_client.set_holding(2000, regs(HOLDING_ON))
    gateway = D3netGateway(lambda: fake_client, 1)
    unit = D3netUnit(gateway, 0, UnitCapability([0, 0, 0]), UnitStatus(regs(STATUS_OFF)))

    async def turn_on():
        await unit.async_write_prepare()
        unit.status.power = True
        await unit.async_write_commit()

    asyncio.run(turn_on())
    powers = [UnitHolding(values).power for _, _, values in fake_client.writes]
    assert powers == [False, True]
    assert _gaps(fake_client.writes)[0] >= INTERVAL - SLACK


def test_filter_reset_writes_are_spaced(fake_client):
    # Holding already matches status, so prepare has nothing to sync.
    fake_client.set_input(2000, regs(STATUS_OFF))
    fake_client.set_holding(2000, _holding(False).registers)  # power off
    gateway = D3netGateway(lambda: fake_client, 1)
    unit = D3netUnit(gateway, 0, UnitCapability([0, 0, 0]), UnitStatus(regs(STATUS_OFF)))

    async def reset_filter():
        await unit.async_write_prepare()
        unit.filter_reset()
        await unit.async_write_commit()

    asyncio.run(reset_filter())
    assert len(fake_client.writes) == 2
    assert [UnitHolding(values).filter_reset for _, _, values in fake_client.writes] == [
        True,
        False,
    ]
    assert _gaps(fake_client.writes)[0] >= INTERVAL - SLACK
