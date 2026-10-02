"""tDSDO: SCK falling edge to SDO data valid delay, data sheet Table 3 maximum 8 ns.

Read frame only. The SDO compare strobe is moved from 20 ns after the SCK falling edge down toward the edge itself.
Data bits 0x55/0xAA make SDO toggle on every clock. The device passes the spec if every bit is already valid
when strobed 8 ns after the falling edge; the boundary (earliest strobe that still reads correctly) is the
measured tDSDO. Compare levels are 0.2/0.8 x VIO (data sheet Figure 2). Accuracy depends on fixture deskew
and on the SDO load versus the 20 pF used for the data sheet number.
"""
from dataclasses import replace

from spi_timing.harness import run_timing_test
from spi_timing.instrument import clock_frame, nominal_cycle
from spi_timing.sweep import ParamSpec


def _timing(strobe_after_fall_ns, s):
    n = nominal_cycle(s)
    return clock_frame(s, replace(n, sdo_strobe=n.sck_fall + strobe_after_fall_ns))


SPEC = ParamSpec(
    symbol="tDSDO", description="SCK falling edge to SDO data valid delay", limit_ns=8.0,
    baseline_ns=20.0, end_ns=0.0, coarse_step_ns=1.0, timing_for=_timing, modes=("read",),
    limit_text="<= 8 ns",
)


def test_tdsdo(probe, setup):
    run_timing_test(SPEC, probe, setup)
