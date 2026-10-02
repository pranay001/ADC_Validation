"""tSSDI: SDI valid setup time to SCK rising edge, data sheet Table 3 minimum 2 ns.

Nominal SCK cycle (rising edge at 60 ns); SDI changes at (rising edge - setup) in every clock cycle of the
stressed frame (instruction and data phase). The hold side is untouched (previous bit held for 100 - setup ns).
Values 0x55/0xAA make every data bit toggle. The sweep goes through 0 ns to -3 ns (SDI changing after the
clock edge) so the negative control can see a violation.
"""
from dataclasses import replace

from spi_timing.harness import run_timing_test
from spi_timing.instrument import clock_frame, nominal_cycle
from spi_timing.sweep import ParamSpec


def _timing(setup_ns, s):
    n = nominal_cycle(s)
    return clock_frame(s, replace(n, sdi_change=n.sck_rise - setup_ns))


SPEC = ParamSpec(
    symbol="tSSDI", description="SDI setup to SCK rising edge", limit_ns=2.0,
    baseline_ns=20.0, end_ns=-3.0, coarse_step_ns=1.0, timing_for=_timing,
)


def test_tssdi(probe, setup):
    run_timing_test(SPEC, probe, setup)
