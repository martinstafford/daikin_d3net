"""DIIINet constants."""

from enum import Enum


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


class D3netFanDirectionCapability(Enum):
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


class D3netRegisterType(Enum):
    """Type of Modbus resgister."""

    Input = "input"
    Holding = "holding"


class D3netVentilationMode(Enum):
    """HRV / VAM ventilation operation mode (input 32804 / holding 42404 bits 7-6)."""

    NONE = 0
    AUTO = 1
    ENERGY_RECLAIM = 2
    BYPASS = 3


class D3netCoolHeatMaster(Enum):
    """Cool/heat master status of an indoor unit."""

    UNKNOWN = 0
    SLAVE = 1
    MASTER = 2


class D3netOperationStatus(Enum):
    """Actual running status (input 32002 bits 11-8)."""

    FAN = 0
    HEATING = 1
    COOLING = 2
