"""Helpers shared by the functional (register-level) tests."""
from __future__ import annotations

import pytest

from .bus import RegisterBus, RunResult, Script
from .registers import DEVICE_STATUS, SPI_STATUS

SIMULATED = "simulated instrument: script compiled and executed, results not evaluated (no DUT)"


def run_or_skip(bus: RegisterBus, script: Script) -> RunResult:
    """Run the script. With a simulated instrument there is no DUT behind SDO, so evaluating it would be
    meaningless: the test skips after proving the pattern compiles, loads and bursts."""
    result = bus.run(script)
    if bus.simulated:
        pytest.skip(SIMULATED)
    return result


def clear_spi_status(script: Script) -> Script:
    """SPI_STATUS error bits are write-1-to-clear."""
    return script.write(SPI_STATUS.addr, 0xFF)


def read_status(script: Script) -> tuple[int, int]:
    """Append reads of SPI_STATUS and DEVICE_STATUS; returns their handles."""
    return script.read(SPI_STATUS.addr), script.read(DEVICE_STATUS.addr)


def hexs(values) -> str:
    return "[" + ", ".join(f"0x{v:02X}" for v in values) + "]"
