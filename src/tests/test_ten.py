"""tEN: CS falling edge to interface ready, data sheet Table 3 maximum 15 ns.

The delay from CS falling to the first SCK falling edge is swept down from 40 ns to 1 ns: the device must
accept the frame when SCK starts 15 ns after CS. CS falls in the lead cycle; the first SCK fall is placed 0.4 ns
into the first clock cycle, so delay = (period - CS change) + 0.4 ns. Both frame types are stressed (the read frame
also needs the SDO output stage ready for the first data bits).
"""
from dataclasses import replace

from spi_timing.harness import run_timing_test
from spi_timing.instrument import clock_frame, nominal_cycle, nominal_frame
from spi_timing.sweep import ParamSpec

FIRST_FALL_NS = 0.4


def _timing(delay_ns, s):
    n = nominal_cycle(s)
    lead = replace(nominal_frame(s).lead, cs_change=n.period - (delay_ns - FIRST_FALL_NS))
    first = replace(n, sck_fall=FIRST_FALL_NS, sdi_change=FIRST_FALL_NS,
                    sdo_strobe=FIRST_FALL_NS + s.nominal_sdo_strobe_after_fall_ns)
    return clock_frame(s, n, lead=lead, first=first)


SPEC = ParamSpec(
    symbol="tEN", description="CS falling edge to interface ready", limit_ns=15.0,
    baseline_ns=40.0, end_ns=1.0, coarse_step_ns=2.0, timing_for=_timing, limit_text="<= 15 ns",
)


def test_ten(probe, setup):
    run_timing_test(SPEC, probe, setup)
