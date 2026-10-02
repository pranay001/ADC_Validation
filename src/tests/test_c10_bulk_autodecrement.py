"""C10: bulk register access in autodecrement mode (default): one frame reads or writes consecutive registers.

The 16 ACC_DEPTH_INn registers (0x0186 to 0x0195, six writable bits each) are used. In autodecrement mode the address in the
instruction phase is decremented after every data byte, so a frame starting at 0x0195 touches IN15, IN14, ... IN0.
  * after 16 single writes of distinct values, one 16-byte bulk read must return them in descending address order;
  * one 16-byte bulk write of different values must be visible in 16 single reads.
"""
from spi_timing.bus import Script
from spi_timing.functional import hexs, run_or_skip
from spi_timing.registers import ACC_DEPTH_IN

MASK = 0x3F
FIRST = [(n * 5 + 3) & MASK for n in range(16)]            # value written to ACC_DEPTH_INn
SECOND = [(~v) & MASK for v in FIRST]
TOP = ACC_DEPTH_IN[15].addr                                # 0x0195


def test_bulk_autodecrement(bus):
    s = Script().hw_reset()
    for n, reg in enumerate(ACC_DEPTH_IN):
        s.write(reg.addr, FIRST[n])
    bulk_read = s.bulk_read(TOP, 16)
    s.write(TOP, [SECOND[15 - i] for i in range(16)])      # bulk write: bytes go to IN15 first, IN0 last
    singles = [s.read(reg.addr) for reg in ACC_DEPTH_IN]
    res = run_or_skip(bus, s)

    expected = [FIRST[15 - i] for i in range(16)]
    got = [b & MASK for b in res[bulk_read].data]
    assert got == expected, f"bulk read {hexs(got)}, expected {hexs(expected)}"
    after = [res[h].value & MASK for h in singles]
    assert after == SECOND, f"after bulk write, single reads {hexs(after)}, expected {hexs(SECOND)}"
