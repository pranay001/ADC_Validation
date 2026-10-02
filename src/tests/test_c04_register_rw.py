"""C4: every writable register stores and returns what is written (data and address path of the register file).

Only bits that are safe to change with the ADC idle are written (Reg.walk_mask; see registers.py for the registers that are
never written). Three passes after a hardware reset:
  A. walking values on each single register (all-0, all-1, 0x55/0xAA pattern, each bit alone, each bit cleared),
     written and read back one register at a time;
  B. a different pseudo-random value in EVERY register, then read all back (catches address aliasing and
     neighbour corruption, including the 128-byte AS_SLOTn memory);
  C. the bitwise complement of pass B, read all back.
Read-back is compared over the walk mask only. A hardware reset at the end restores the defaults.
"""
from spi_timing.bus import Script
from spi_timing.functional import run_or_skip
from spi_timing.registers import AS_SLOT, CONFIG_IN, WALKABLE

ARRAYS = set(AS_SLOT) | set(CONFIG_IN)


def _walk_values(mask: int, width_bits: int) -> list[int]:
    values = {0, mask, 0x5555_5555 & mask, 0xAAAA_AAAA & mask}
    for bit in range(width_bits):
        if mask >> bit & 1:
            values |= {1 << bit, mask & ~(1 << bit)}
    return sorted(values)


def _scramble(addr: int) -> int:
    return ((addr * 40503) >> 3) ^ (addr * 7)


def test_register_read_write(bus):
    s = Script().hw_reset()
    checks = []                                          # (description, register, handle, expected)

    for reg in (r for r in WALKABLE if r not in ARRAYS):                           # pass A
        for v in _walk_values(reg.walk, 8 * reg.nbytes):
            s.write(reg.addr, v, reg.nbytes)
            checks.append((f"A {reg.name} wrote 0x{v:0{2 * reg.nbytes}X}", reg, s.read(reg.addr, reg.nbytes), v & reg.walk))

    for label, transform in (("B", lambda v: v), ("C", lambda v: ~v)):            # passes B and C
        expected = {}
        for reg in WALKABLE:
            v = transform(_scramble(reg.addr)) & reg.walk
            expected[reg] = v
            s.write(reg.addr, v, reg.nbytes)
        for reg in WALKABLE:
            checks.append((f"{label} {reg.name}", reg, s.read(reg.addr, reg.nbytes), expected[reg]))
    s.hw_reset()
    res = run_or_skip(bus, s)

    failures = []
    for desc, reg, handle, want in checks:
        got = res[handle].value & reg.walk
        if got != want:
            failures.append(f"{desc}: read 0x{got:0{2 * reg.nbytes}X}, expected 0x{want:0{2 * reg.nbytes}X}")
    assert not failures, f"{len(failures)} of {len(checks)} read-backs differ:\n" + "\n".join(failures[:40])
