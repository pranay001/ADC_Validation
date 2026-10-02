"""tHSDI: SDI valid hold time after SCK rising edge, data sheet Table 3 minimum 2 ns.

The SCK rising edge is placed 0.4 ns before the end of the cycle and SDI changes in the next cycle at
(hold - 0.4 ns), so the hold of each bit equals the swept value and its setup is 100 - hold ns. The edge
placement limits the sweep to holds >= 0.4 ns; the sweep ends at 0.5 ns, so the negative control may not see
a violation (the report says so).

The hold of bit k is set by SDI timing of cycle k+1, so the LAST cycle keeps nominal timing: hold is stressed
on clock bits 0..21 (including all data-phase transitions but the final one).
"""
from dataclasses import replace

from spi_timing.harness import run_timing_test
from spi_timing.instrument import clock_frame, nominal_cycle
from spi_timing.sweep import ParamSpec

RISE_TO_END_NS = 0.4
LOW_NS = 40.0


def _timing(hold_ns, s):
    n = nominal_cycle(s)
    fall = n.period - LOW_NS - RISE_TO_END_NS
    stressed = replace(n, sck_fall=fall, sck_low=LOW_NS, sdi_change=hold_ns - RISE_TO_END_NS,
                       sdo_strobe=fall + s.nominal_sdo_strobe_after_fall_ns)
    return clock_frame(s, stressed, last=n)


SPEC = ParamSpec(
    symbol="tHSDI", description="SDI hold after SCK rising edge", limit_ns=2.0,
    baseline_ns=20.0, end_ns=0.5, coarse_step_ns=1.0, timing_for=_timing,
)


def test_thsdi(probe, setup):
    run_timing_test(SPEC, probe, setup)
