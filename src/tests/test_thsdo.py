"""tHSDO: SCK falling edge to SDO data remains valid, data sheet Table 3 minimum 2 ns.

Read frame only. The SDO strobe is placed after the SCK falling edge but the pattern expects the PREVIOUS data
bit (compare mode 'previous', clock cycles 17..23), so the compare passes only while the old bit is still
held. The strobe is moved later from 0.5 ns; the last strobe offset that still reads the previous bit is the
measured tHSDO. The sweep ends at 12 ns, past tDSDO max, where the new bit has certainly replaced the old
one (the negative control). Accuracy depends on fixture deskew and the SDO load.
"""
from dataclasses import replace

from spi_timing.harness import run_timing_test
from spi_timing.instrument import clock_frame, nominal_cycle
from spi_timing.sweep import ParamSpec


def _timing(strobe_after_fall_ns, s):
    n = nominal_cycle(s)
    return clock_frame(s, replace(n, sdo_strobe=n.sck_fall + strobe_after_fall_ns))


SPEC = ParamSpec(
    symbol="tHSDO", description="SCK falling edge to SDO data remains valid", limit_ns=2.0,
    baseline_ns=0.5, end_ns=12.0, coarse_step_ns=1.0, timing_for=_timing, direction="max",
    modes=("read",), sdo_expect="previous",
)


def test_thsdo(probe, setup):
    run_timing_test(SPEC, probe, setup)
