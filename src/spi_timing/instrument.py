"""NI digital pattern instrument session, time-set programming and the pass/fail probe."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import hightime
import nidigital
from nidigital import DriveFormat, TimeSetEdgeType as Edge

from .config import ROOT, Setup
from .patterns import (FRAMES, NOM_TIMESET, PATTERN_NAME, ROLES, compile_pattern, probe_source,
                       timeset_name)

EDGE_MARGIN_NS = 0.2   # keep programmed edges this far inside the cycle


@dataclass(frozen=True)
class CycleTiming:
    """Edge placement inside one cycle, all in ns from the start of the cycle.

    SCK idles high (SPI mode 3): it falls at `sck_fall`, rises at `sck_fall + sck_low`.
      low time  = sck_low
      high time = period - sck_low   (between this cycle's rising edge and the next falling edge)
    SDI changes at `sdi_change`; SDO is strobed at `sdo_strobe`; CS changes at `cs_change` in the cycles
    where CS makes a transition (LEAD: falls, LAST: rises).
    """
    period: float
    sck_fall: float
    sck_low: float
    sdi_change: float
    sdo_strobe: float
    cs_change: float

    @property
    def sck_rise(self) -> float:
        return self.sck_fall + self.sck_low

    @property
    def sck_high(self) -> float:
        return self.period - self.sck_low

    def validate(self) -> None:
        limit = self.period - EDGE_MARGIN_NS
        if not (0 < self.sck_fall and self.sck_low > 0 and self.sck_rise < limit):
            raise ValueError(f"SCK edges do not fit in the cycle: {self}")
        if not (0 <= self.sdi_change < limit and 0 < self.sdo_strobe < limit and 0 <= self.cs_change < limit):
            raise ValueError(f"SDI change / SDO strobe / CS change do not fit in the cycle: {self}")


@dataclass(frozen=True)
class FrameTiming:
    """Timing of the four cycle roles of one frame (see patterns.py)."""
    lead: CycleTiming
    first: CycleTiming
    mid: CycleTiming
    last: CycleTiming

    def by_role(self) -> dict[str, CycleTiming]:
        return dict(zip(ROLES, (self.lead, self.first, self.mid, self.last)))


def nominal_cycle(setup: Setup) -> CycleTiming:
    return CycleTiming(setup.nominal_period_ns, setup.nominal_sck_fall_ns, setup.nominal_sck_low_ns,
                       setup.nominal_sdi_change_ns,
                       setup.nominal_sck_fall_ns + setup.nominal_sdo_strobe_after_fall_ns,
                       setup.nominal_cs_last_change_ns)


def nominal_frame(setup: Setup) -> FrameTiming:
    n = nominal_cycle(setup)
    return FrameTiming(lead=replace(n, cs_change=setup.nominal_cs_lead_change_ns), first=n, mid=n, last=n)


def clock_frame(setup: Setup, cycle: CycleTiming, **roles: CycleTiming) -> FrameTiming:
    """Nominal LEAD, `cycle` for the clock cycles FIRST/MID/LAST; `roles` overrides individual roles."""
    f = replace(nominal_frame(setup), first=cycle, mid=cycle, last=cycle)
    return replace(f, **roles)


def sck_cycle(setup: Setup, period_ns: float, low_ns: float) -> CycleTiming:
    """Stressed SCK cycle with the given period and low time (high time = period - low).

    SDI changes on the SCK falling edge, so its setup to the next rising edge equals the low time and its
    hold after the previous rising edge equals the high time: both stay well above the 2 ns minimum over
    the swept ranges. SDO is strobed `sdo_strobe_ns` after the SCK falling edge (data sheet tDSDO max 8 ns).
    `cs_change` is unused here (CS only moves in the LEAD and LAST cycles); see `sck_frame` for the LAST cycle.
    """
    fall = (period_ns - low_ns) / 2
    return CycleTiming(period_ns, fall, low_ns, fall, fall + setup.sdo_strobe_ns, 0.0)


LAST_CYCLE_EXTENSION_NS = 30.0


def sck_frame(setup: Setup, period_ns: float, low_ns: float) -> FrameTiming:
    """Frame whose clock cycles all use `sck_cycle(period, low)`.

    The LAST cycle is lengthened so CS can rise well after its SCK rising edge (>= 10 ns, 5x tSCKCSB) and after the
    SDO strobe, without touching what is under test: the high time before the last falling edge and the low
    time of the last pulse only depend on the cycle start and the edge offsets, not on the cycle length.
    """
    c = sck_cycle(setup, period_ns, low_ns)
    last = replace(c, period=c.period + LAST_CYCLE_EXTENSION_NS,
                   cs_change=max(c.sck_rise + 10.0, c.sdo_strobe + 2.0))
    return clock_frame(setup, c, last=last)


def _td(ns: float) -> hightime.timedelta:
    return hightime.timedelta(seconds=ns * 1e-9)


def program_timeset(session: nidigital.Session, name: str, t: CycleTiming) -> None:
    t.validate()
    session.configure_time_set_period(name, _td(t.period))
    off = t.period - EDGE_MARGIN_NS / 2
    sck = session.pins["SCK"]
    sck.configure_time_set_drive_format(name, DriveFormat.RH)
    for edge, value in ((Edge.DRIVE_ON, 0.0), (Edge.DRIVE_DATA, t.sck_fall),
                        (Edge.DRIVE_RETURN, t.sck_rise), (Edge.DRIVE_OFF, off)):
        sck.configure_time_set_edge(name, edge, _td(value))
    for pin, change in (("CS", t.cs_change), ("SDI", t.sdi_change)):
        p = session.pins[pin]
        p.configure_time_set_drive_format(name, DriveFormat.NR)
        for edge, value in ((Edge.DRIVE_ON, 0.0), (Edge.DRIVE_DATA, change), (Edge.DRIVE_OFF, off)):
            p.configure_time_set_edge(name, edge, _td(value))
    session.pins["SDO"].configure_time_set_edge(name, Edge.COMPARE_STROBE, _td(t.sdo_strobe))


def program_frame(session: nidigital.Session, frame: str, timing: FrameTiming) -> None:
    for role, cycle in timing.by_role().items():
        program_timeset(session, timeset_name(frame, role), cycle)


class Probe:
    """Runs the scratch-pad write/readback loop with a chosen timing on the write and read frames."""

    def __init__(self, setup: Setup, sdo_expect: str = "current", name: str = "probe"):
        self.setup = setup
        self.sdo_expect = sdo_expect
        self.build_dir: Path = ROOT / "build" / name
        self.nominal = nominal_frame(setup)
        self.session: nidigital.Session | None = None

    def open(self) -> "Probe":
        s = self.setup
        options = {"simulate": True, "driver_setup": {"Model": s.model}} if s.simulate else {}
        self.session = nidigital.Session(s.resource, options=options)
        self.session.load_pin_map(str(s.pinmap))
        self.session.configure_voltage_levels(vil=0.2 * s.vio, vih=0.8 * s.vio, vol=0.2 * s.vio,
                                              voh=0.8 * s.vio, vterm=0.5 * s.vio)
        self.session.create_time_set(NOM_TIMESET)
        program_timeset(self.session, NOM_TIMESET, self.nominal.mid)
        for frame in FRAMES:
            for role in ROLES:
                self.session.create_time_set(timeset_name(frame, role))
            program_frame(self.session, frame, self.nominal)
        source = probe_source(s.frames_per_point, sdo_expect=self.sdo_expect)
        pattern = compile_pattern(source, self.build_dir, s.pinmap, s.compiler)
        self.session.load_pattern(str(pattern))
        return self

    def close(self) -> None:
        if self.session is not None:
            self.session.close()
            self.session = None

    def run(self, write: FrameTiming | None = None, read: FrameTiming | None = None) -> bool:
        """True when every SDO compare in every frame matched. None means nominal timing."""
        assert self.session is not None, "call open() first"
        program_frame(self.session, "WR", write or self.nominal)
        program_frame(self.session, "RD", read or self.nominal)
        self.session.burst_pattern(PATTERN_NAME, timeout=_td(60e9))
        return all(self.session.get_site_pass_fail().values())
