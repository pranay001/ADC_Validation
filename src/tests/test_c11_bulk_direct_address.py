"""C11: direct-address mode (SPI_CONFIG_B.INST_MODE = 1): several instruction + data groups inside one CS frame.

In direct-address mode the host sends a new instruction after every REG_DATA, so one frame can touch non-adjacent
registers. In one frame: write SCRATCH_PAD, read ACC_MASK_1 (default 0xFE), read SCRATCH_PAD back, read ACC_MASK_2 (default 0xFF),
read ACC_DEPTH_IN3 and ACC_DEPTH_IN0 (default 0x3F). Then INST_MODE is cleared and an autodecrement bulk read of two registers
confirms the device is back in the default mode.
"""
from spi_timing.bus import Script
from spi_timing.functional import hexs, run_or_skip
from spi_timing.registers import ACC_DEPTH_IN, ACC_MASK_1, ACC_MASK_2, SCRATCH_PAD, SPI_CONFIG_B

INST_MODE = 0x80


def test_direct_address_mode(bus):
    s = Script().hw_reset()
    s.write(SPI_CONFIG_B.addr, INST_MODE)
    mode = s.read(SPI_CONFIG_B.addr)
    h = s.multi(("w", SCRATCH_PAD.addr, 0xA5), ("r", ACC_MASK_1.addr, 1), ("r", SCRATCH_PAD.addr, 1),
                ("r", ACC_MASK_2.addr, 1), ("r", ACC_DEPTH_IN[3].addr, 1), ("r", ACC_DEPTH_IN[0].addr, 1))
    s.write(SPI_CONFIG_B.addr, 0x00)                                   # back to autodecrement
    s.write(ACC_MASK_1.addr, 0x11).write(ACC_MASK_2.addr, 0x22)
    bulk = s.bulk_read(ACC_MASK_2.addr, 2)                             # ACC_MASK_2 (0x0185), then ACC_MASK_1 (0x0184)
    res = run_or_skip(bus, s)

    assert res[mode].value == INST_MODE, f"SPI_CONFIG_B reads 0x{res[mode].value:02X} after setting INST_MODE"
    got = [res[x].value for x in h]
    expected = [ACC_MASK_1.reset, 0xA5, ACC_MASK_2.reset, 0x3F, 0x3F]
    assert got == expected, f"direct-address frame returned {hexs(got)}, expected {hexs(expected)}"
    assert res[bulk].data == [0x22, 0x11], f"autodecrement mode not restored: bulk read {hexs(res[bulk].data)}"
