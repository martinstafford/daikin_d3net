"""Holding registers kept in sync with status while polling (CB13A033 p13).

The DTA116A51 only sends a command when a holding register value changes, and
changes made at a wall controller don't update the holding registers. The BMS
has to copy status into holding when it reads status, "otherwise an operation
from the HA system will be ignored".
"""

import asyncio

from conftest import regs
from d3net.encoding import UnitCapability, UnitHolding, UnitStatus
from d3net.gateway import CACHE_WRITE, D3netGateway, D3netUnit

PROPS = D3netUnit.SYNC_PROPERTIES

# Real registers from a unit before and after being turned off at the wall.
STATUS_ON = (
    "0001000000000001 0100001000010010 0000000011110000 "
    "0000000000000000 0000000011101000 1000000000000000"
)
STATUS_OFF = (
    "0001000000000000 0100001000010010 0000000011110000 "
    "0000000000000000 0000000011101000 1000000000000000"
)
HOLDING_ON = "0001000001100001 0000001000000010 0000000011110000"
HOLDING_OFF = "0001000001100000 0000001000000010 0000000011110000"


def _unit(fake_client, status: str, holding: str) -> D3netUnit:
    fake_client.set_input(2000, regs(status))
    fake_client.set_holding(2000, regs(holding))
    gateway = D3netGateway(lambda: fake_client, 1)
    return D3netUnit(gateway, 0, UnitCapability([0, 0, 0]), UnitStatus(regs(status)))


def test_differs_detects_a_stale_power_bit_without_changing_anything():
    holding = UnitHolding(regs(HOLDING_ON))
    assert holding.differs(UnitStatus(regs(STATUS_OFF)), PROPS)
    assert holding.registers == regs(HOLDING_ON)
    assert not holding.dirty


def test_differs_is_false_when_in_sync():
    assert not UnitHolding(regs(HOLDING_ON)).differs(UnitStatus(regs(STATUS_ON)), PROPS)
    assert not UnitHolding(regs(HOLDING_OFF)).differs(UnitStatus(regs(STATUS_OFF)), PROPS)


def test_written_without_timestamp_does_not_start_read_delay():
    holding = UnitHolding(regs(HOLDING_ON))
    holding.power = False
    holding.written(timestamp=False)
    assert not holding.dirty
    assert not holding.writeWithin(CACHE_WRITE)


def test_poll_after_wall_change_syncs_holding_once(fake_client):
    # HA last turned the unit on; it has since been turned off at the wall.
    unit = _unit(fake_client, STATUS_OFF, HOLDING_ON)

    asyncio.run(unit.async_update_status())

    # One write, copying the unit's state: only the power bit changes.
    assert [(address, values) for _, address, values in fake_client.writes] == [
        (2000, regs(HOLDING_OFF))
    ]
    # Polling carries on as normal: the sync write isn't a command.
    assert not unit._holding.writeWithin(CACHE_WRITE)

    # Nothing more to do on later polls, and holding isn't re-read.
    asyncio.run(unit.async_update_status())
    assert len(fake_client.writes) == 1
    assert len(fake_client.holding_reads) == 1


def test_poll_in_sync_writes_nothing(fake_client):
    unit = _unit(fake_client, STATUS_ON, HOLDING_ON)

    asyncio.run(unit.async_update_status())
    asyncio.run(unit.async_update_status())

    assert fake_client.writes == []
    assert len(fake_client.holding_reads) == 1


def test_command_after_wall_change_is_a_single_write(fake_client):
    """The failure case from #16, with the poll in between.

    HA turned the unit on, someone turned it off at the wall, a poll saw that,
    and HA turns it on again. The command must be a real change of the holding
    register, not a sync write followed by a write back to the old value.
    """
    unit = _unit(fake_client, STATUS_OFF, HOLDING_ON)
    asyncio.run(unit.async_update_status())
    fake_client.writes.clear()

    async def turn_on():
        await unit.async_write_prepare()
        unit.status.power = True
        await unit.async_write_commit()

    asyncio.run(turn_on())
    assert [UnitHolding(values).power for _, _, values in fake_client.writes] == [True]


def test_no_sync_while_a_command_is_pending(fake_client):
    # Right after a command the unit still reports its old state. A poll then
    # must not copy that back into holding, which would cancel the command.
    unit = _unit(fake_client, STATUS_OFF, HOLDING_OFF)

    async def turn_on_then_poll():
        await unit.async_write_prepare()
        unit.status.power = True
        await unit.async_write_commit()
        await unit.async_update_status()

    asyncio.run(turn_on_then_poll())
    assert [UnitHolding(values).power for _, _, values in fake_client.writes] == [True]
    assert fake_client.holding[2000] & 1  # still on


def test_failed_sync_is_retried_on_the_next_poll(fake_client):
    unit = _unit(fake_client, STATUS_OFF, HOLDING_ON)

    fake_client.fail_writes = True
    asyncio.run(unit.async_update_status())  # must not raise
    assert unit.status.power is False
    assert fake_client.writes == []

    fake_client.fail_writes = False
    asyncio.run(unit.async_update_status())
    assert [values for _, _, values in fake_client.writes] == [regs(HOLDING_OFF)]
    # Holding was read again after the failure.
    assert len(fake_client.holding_reads) == 2
