"""C6: access to an undefined register address sets SPI_STATUS.INVALID_ADDR_ERROR (bit 0).

Seven addresses in gaps of the map and beyond its end are read and written; each must set the flag, which stays set until
cleared with a write of 1. The highest defined address (0x02BF) must be readable without raising the flag.
"""
from spi_timing.bus import Script
from spi_timing.functional import clear_spi_status, run_or_skip
from spi_timing.registers import HIGHEST_VALID_ADDRESS, INVALID_ADDR_ERROR, SPI_STATUS, UNDEFINED_ADDRESSES


def test_invalid_address_flag(bus):
    s = Script().hw_reset()
    clear_spi_status(s)
    cases = []
    for addr in UNDEFINED_ADDRESSES:
        s.read(addr)
        after_read = s.read(SPI_STATUS.addr)
        clear_spi_status(s)
        s.write(addr, 0x5A)
        after_write = s.read(SPI_STATUS.addr)
        clear_spi_status(s)
        cleared = s.read(SPI_STATUS.addr)
        cases.append((addr, after_read, after_write, cleared))
    s.read(HIGHEST_VALID_ADDRESS)
    valid = s.read(SPI_STATUS.addr)
    res = run_or_skip(bus, s)

    for addr, after_read, after_write, cleared in cases:
        assert res[after_read].value & INVALID_ADDR_ERROR, f"read of undefined 0x{addr:04X}: flag not set"
        assert res[after_write].value & INVALID_ADDR_ERROR, f"write to undefined 0x{addr:04X}: flag not set"
        assert not res[cleared].value & INVALID_ADDR_ERROR, f"flag for 0x{addr:04X} not cleared by writing 1"
    assert not res[valid].value & INVALID_ADDR_ERROR, f"valid address 0x{HIGHEST_VALID_ADDRESS:04X} raised INVALID_ADDR_ERROR"
