"""tCSBH: CS high time, data sheet Table 3 minimum 10 ns.

CS high time between the stressed write frame and the readback frame that follows it directly (there are no idle
cycles in the pattern). CS rises in the last cycle of the write at (period - high time) and falls at the start of
the read frame's lead cycle. A CS pulse that is too short either leaves the write uncommitted or the read
mis-framed; both show as a wrong readback. Write-to-read gap only: the read-to-write boundary is not stressed.
"""
from dataclasses import replace

from spi_timing.harness import run_timing_test
from spi_timing.instrument import nominal_cycle, nominal_frame
from spi_timing.sweep import ParamSpec


def _timing(high_ns, s):
    n = nominal_cycle(s)
    return replace(nominal_frame(s), last=replace(n, cs_change=n.period - high_ns))


SPEC = ParamSpec(
    symbol="tCSBH", description="CS high time", limit_ns=10.0,
    baseline_ns=20.0, end_ns=1.0, coarse_step_ns=1.0, timing_for=_timing, modes=("write",),
)


def test_tcsbh(probe, setup):
    run_timing_test(SPEC, probe, setup)
