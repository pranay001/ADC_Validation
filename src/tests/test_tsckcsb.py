"""tSCKCSB: SCK rising edge to CS rising edge, data sheet Table 3 minimum 2 ns.

Write frame only: CS rises in the last clock cycle at (last SCK rising edge + gap). Negative gaps (CS rising
before the last SCK edge) are swept to -5 ns; the last data bit is then not clocked, the register write is
incomplete and ignored, and the readback shows the old value. In a read frame the last SDO bit is already
strobed before CS rises, so the read frame carries no information for this parameter.
"""
from dataclasses import replace

from spi_timing.harness import run_timing_test
from spi_timing.instrument import nominal_cycle, nominal_frame
from spi_timing.sweep import ParamSpec


def _timing(gap_ns, s):
    n = nominal_cycle(s)
    return replace(nominal_frame(s), last=replace(n, cs_change=n.sck_rise + gap_ns))


SPEC = ParamSpec(
    symbol="tSCKCSB", description="SCK rising edge to CS rising edge", limit_ns=2.0,
    baseline_ns=20.0, end_ns=-5.0, coarse_step_ns=1.0, timing_for=_timing, modes=("write",),
)


def test_tsckcsb(probe, setup):
    run_timing_test(SPEC, probe, setup)
