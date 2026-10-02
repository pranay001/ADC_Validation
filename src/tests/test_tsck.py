"""tSCK: SCK period, data sheet Table 3 minimum 32 ns (SPI mode 3, all modes except manual).

Every SCK cycle of the stressed frame (instruction and data phase) uses the swept period with a 50% duty
cycle, so low = high = period / 2. The sweep ends at 20 ns, where tSCKL/tSCKH (10 ns each) would start to
dominate. Baseline is 2x the limit.
"""
from spi_timing.harness import run_timing_test
from spi_timing.instrument import sck_frame
from spi_timing.sweep import ParamSpec

SPEC = ParamSpec(
    symbol="tSCK", description="SCK period", limit_ns=32.0,
    baseline_ns=64.0, end_ns=20.0, coarse_step_ns=2.0,
    timing_for=lambda period, s: sck_frame(s, period_ns=period, low_ns=period / 2),
)


def test_tsck(probe, setup):
    run_timing_test(SPEC, probe, setup)
