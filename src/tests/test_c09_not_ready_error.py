"""C9: a frame sent before the device is ready sets SPI_STATUS.NOT_RDY_ERROR (bit 7).

Hardware reset, then a scratch pad write only 20 us after the RESET falling edge (the data sheet gives tHWR = 300 us typical).
After waiting for the device, NOT_RDY_ERROR must be set and the write must have been ignored (SCRATCH_PAD still 0x00).
The bit is sticky and clears when 1 is written to it. If the device clears SPI_STATUS at the end of its reset, this test
needs adjusting on the bench (the data sheet only says the bit is set by a transaction before the device is ready).
"""
from spi_timing.bus import HW_RESET_LOW_NS, HW_RESET_WAIT_NS, Script
from spi_timing.functional import run_or_skip
from spi_timing.registers import NOT_RDY_ERROR, SCRATCH_PAD, SPI_STATUS

TOO_EARLY_NS = 20_000.0


def test_not_ready_error(bus):
    s = Script().hw_reset(low_ns=HW_RESET_LOW_NS, wait_ns=TOO_EARLY_NS)
    s.write(SCRATCH_PAD.addr, 0xA5)                                       # sent while the device is still resetting
    s.wait(HW_RESET_WAIT_NS)
    flags = s.read(SPI_STATUS.addr)
    value = s.read(SCRATCH_PAD.addr)
    s.write(SPI_STATUS.addr, NOT_RDY_ERROR)
    cleared = s.read(SPI_STATUS.addr)
    res = run_or_skip(bus, s)

    assert res[flags].value & NOT_RDY_ERROR, f"NOT_RDY_ERROR not set (SPI_STATUS = 0x{res[flags].value:02X})"
    assert res[value].value == 0x00, f"write before ready was accepted: SCRATCH_PAD = 0x{res[value].value:02X}"
    assert not res[cleared].value & NOT_RDY_ERROR, "NOT_RDY_ERROR not cleared by writing 1"
