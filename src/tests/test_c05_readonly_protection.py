"""C5: writing a register that contains only read-only bits is ignored and flagged (SPI_STATUS.INVALID_WR_ERROR, bit 2).

For DEVICE_TYPE, PRODUCT_ID_LSB, VENDOR_ID_LSB and VENDOR_ID_MSB: write 0xFF, then the register must still hold its value and
SPI_STATUS bit 2 must be set (and DEVICE_STATUS.SPI_ERROR, bit 2, as the OR of all SPI_STATUS flags). Writing 1 to the flag
clears it again.
"""
from spi_timing.bus import Script
from spi_timing.functional import clear_spi_status, run_or_skip
from spi_timing.registers import (DEVICE_STATUS, INVALID_WR_ERROR, READ_ONLY_TARGETS, SPI_ERROR, SPI_STATUS)


def test_readonly_registers_ignore_writes(bus):
    s = Script().hw_reset()
    clear_spi_status(s)
    cases = []
    for reg in READ_ONLY_TARGETS:
        before = s.read(reg.addr)
        s.write(reg.addr, 0xFF)
        after = s.read(reg.addr)
        flags = s.read(SPI_STATUS.addr)
        dev = s.read(DEVICE_STATUS.addr)
        s.write(SPI_STATUS.addr, INVALID_WR_ERROR)                    # write 1 to clear
        cleared = s.read(SPI_STATUS.addr)
        cases.append((reg, before, after, flags, dev, cleared))
    res = run_or_skip(bus, s)

    for reg, before, after, flags, dev, cleared in cases:
        assert res[after].value == res[before].value, \
            f"{reg.name} changed by a write: 0x{res[before].value:02X} -> 0x{res[after].value:02X}"
        assert res[flags].value & INVALID_WR_ERROR, f"{reg.name}: INVALID_WR_ERROR not set (SPI_STATUS = 0x{res[flags].value:02X})"
        assert res[dev].value & SPI_ERROR, f"{reg.name}: DEVICE_STATUS.SPI_ERROR not set"
        assert not res[cleared].value & INVALID_WR_ERROR, f"{reg.name}: INVALID_WR_ERROR not cleared by writing 1"
