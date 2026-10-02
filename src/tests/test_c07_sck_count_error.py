"""C7: a data phase that is not a whole number of bytes sets SPI_STATUS.SCK_ERROR (bit 4).

Write frames to the scratch pad (known value 0xA5) with a data phase of 7, 12 and 15 clocks:
  * every case must set SCK_ERROR;
  * the 7-clock case (partial byte) must not modify the register: a partial register write is invalid and ignored.
SCK_ERROR is sticky and clears when 1 is written to it.
"""
from spi_timing.bus import Script
from spi_timing.functional import clear_spi_status, run_or_skip
from spi_timing.registers import SCK_ERROR, SCRATCH_PAD, SPI_STATUS

CASES = {7: "7 data clocks", 12: "12 data clocks", 15: "15 data clocks"}


def test_sck_count_error(bus):
    s = Script().hw_reset()
    s.write(SCRATCH_PAD.addr, 0xA5)
    clear_spi_status(s)
    handles = {}
    for clocks in CASES:
        s.raw_write(SCRATCH_PAD.addr, [0, 1, 0, 1, 1, 1, 1, 0, 1, 0, 1, 1, 0, 0, 1][:clocks])
        flags = s.read(SPI_STATUS.addr)
        value = s.read(SCRATCH_PAD.addr)
        s.write(SPI_STATUS.addr, SCK_ERROR)
        cleared = s.read(SPI_STATUS.addr)
        handles[clocks] = (flags, value, cleared)
        s.write(SCRATCH_PAD.addr, 0xA5)
    res = run_or_skip(bus, s)

    for clocks, (flags, _value, cleared) in handles.items():
        assert res[flags].value & SCK_ERROR, f"{CASES[clocks]}: SCK_ERROR not set (SPI_STATUS = 0x{res[flags].value:02X})"
        assert not res[cleared].value & SCK_ERROR, f"{CASES[clocks]}: SCK_ERROR not cleared by writing 1"
    assert res[handles[7][1]].value == 0xA5, \
        f"partial 7-clock write modified SCRATCH_PAD: 0x{res[handles[7][1]].value:02X}"
