"""tSCKL: SCK low time, data sheet Table 3 minimum 10 ns.

The period is held at 40 ns (above the 32 ns tSCK minimum) so only the low pulse width changes
(high time = 40 ns - low time). Every SCK cycle of the stressed frame (instruction and data phase) is stressed.
"""
from spi_timing.harness import run_timing_test
from spi_timing.instrument import sck_frame
from spi_timing.sweep import ParamSpec

PERIOD_NS = 40.0

SPEC = ParamSpec(
    symbol="tSCKL", description="SCK low time", limit_ns=10.0,
    baseline_ns=20.0, end_ns=4.0, coarse_step_ns=1.0,
    timing_for=lambda low, s: sck_frame(s, period_ns=PERIOD_NS, low_ns=low),
)


def test_tsckl(probe, setup):
    run_timing_test(SPEC, probe, setup)
