"""C1: register reset values after a hardware reset (data sheet Table 24).

Every defined register is read once after RESET and compared, over the bits that do not depend on the analog side,
with the Table 24 reset value. PRODUCT_ID_LSB accepts both AD4691 (0x11) and AD4692 (0x12). Two registers where the data
sheet contradicts itself (CONFIG_INn, STATE_RESET_REG) are reported as warnings, not failures. GPIO_READ (follows the
pin level) and the clamp status registers (analog) are not checked; ACC_STS_SAT_2 is skipped (address looks like a typo).
"""
import warnings

from spi_timing.bus import Script
from spi_timing.functional import run_or_skip
from spi_timing.registers import ALL_REGISTERS


def test_reset_values(bus):
    s = Script().hw_reset()
    handles = {reg: s.read(reg.addr, reg.nbytes) for reg in ALL_REGISTERS}
    res = run_or_skip(bus, s)

    failures, ambiguous = [], []
    for reg, h in handles.items():
        got = res[h].value & reg.mask
        allowed = {(v & reg.mask) for v in (reg.reset, *reg.accept)}
        if got in allowed or reg.mask == 0:
            continue
        line = f"{reg.name} @0x{reg.addr:04X}: read 0x{got:0{2 * reg.nbytes}X}, expected " + \
               " or ".join(f"0x{v:0{2 * reg.nbytes}X}" for v in sorted(allowed))
        (ambiguous if reg.ambiguous_reset else failures).append(line + (f" ({reg.ambiguous_reset})" if reg.ambiguous_reset else ""))
    for line in ambiguous:
        warnings.warn("data sheet ambiguity, not a failure: " + line, stacklevel=2)
    assert not failures, "reset value mismatches:\n" + "\n".join(failures)
