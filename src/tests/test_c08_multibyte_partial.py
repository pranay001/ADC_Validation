"""C8: partial access to a multibyte register sets SPI_STATUS.MB_PARTIAL_ERROR (bit 1).

STD_SEQ_CONFIG is 16 bits wide (MSByte at 0x0025, LSByte at 0x0024) and the only writable multibyte register.
  * a one-byte read starting at 0x0025 (MSByte only) and a one-byte read at 0x0024 (LSByte only, the data sheet example)
    must each set the flag;
  * a one-byte write to 0x0025 must set the flag and leave the register unchanged;
  * a full 16-bit write must take effect and must not set the flag.
"""
from spi_timing.bus import Script
from spi_timing.functional import clear_spi_status, run_or_skip
from spi_timing.registers import MB_PARTIAL_ERROR, SPI_STATUS, STD_SEQ_CONFIG


def test_multibyte_partial_access(bus):
    s = Script().hw_reset()
    clear_spi_status(s)
    s.read(STD_SEQ_CONFIG.addr, 1)
    msb_only = s.read(SPI_STATUS.addr)
    clear_spi_status(s)
    s.read(STD_SEQ_CONFIG.addr - 1, 1)
    lsb_only = s.read(SPI_STATUS.addr)
    clear_spi_status(s)
    s.write(STD_SEQ_CONFIG.addr, 0xFF)                                   # partial write: one byte only
    partial_write = s.read(SPI_STATUS.addr)
    unchanged = s.read(STD_SEQ_CONFIG.addr, 2)
    clear_spi_status(s)
    s.write(STD_SEQ_CONFIG.addr, 0x5AA5, nbytes=2)                      # full 16-bit write
    full_flags = s.read(SPI_STATUS.addr)
    full_value = s.read(STD_SEQ_CONFIG.addr, 2)
    s.hw_reset()
    res = run_or_skip(bus, s)

    assert res[msb_only].value & MB_PARTIAL_ERROR, "one-byte read at 0x0025: MB_PARTIAL_ERROR not set"
    assert res[lsb_only].value & MB_PARTIAL_ERROR, "one-byte read at 0x0024: MB_PARTIAL_ERROR not set"
    assert res[partial_write].value & MB_PARTIAL_ERROR, "one-byte write: MB_PARTIAL_ERROR not set"
    assert res[unchanged].value == STD_SEQ_CONFIG.reset, \
        f"partial write changed STD_SEQ_CONFIG to 0x{res[unchanged].value:04X}"
    assert not res[full_flags].value & MB_PARTIAL_ERROR, "full 16-bit write raised MB_PARTIAL_ERROR"
    assert res[full_value].value == 0x5AA5, f"full write read back 0x{res[full_value].value:04X}"
