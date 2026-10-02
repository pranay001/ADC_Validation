"""Baseline gate, at-spec verdict, coarse sweep + bisection and negative control for one parameter.

A parameter x is swept from a conservative `baseline_ns` toward and past its data sheet limit to `end_ns`.
`direction` says which way is worse:
  "min": the data sheet gives a minimum, x decreasing is worse   (setup, hold, pulse widths, ...)
  "max": the data sheet gives a maximum, x increasing is worse
For the delay-type output specs, x is the SDO strobe offset after the SCK falling edge: tDSDO (data valid
by 8 ns) is "min" in x because an earlier strobe is more demanding, tHSDO (data held for 2 ns) is "max"
in x because a later strobe is more demanding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from .config import Setup
from .instrument import FrameTiming

MODES = ("write", "read")   # which frame of the probe carries the stressed timing


class Runner(Protocol):
    nominal: FrameTiming

    def run(self, write: FrameTiming | None = None, read: FrameTiming | None = None) -> bool: ...


@dataclass(frozen=True)
class ParamSpec:
    symbol: str
    description: str
    limit_ns: float
    baseline_ns: float
    end_ns: float
    coarse_step_ns: float
    timing_for: Callable[[float, Setup], FrameTiming]   # parameter value (ns) -> timing of the frame under test
    direction: str = "min"                              # "min" or "max", see module docstring
    modes: tuple[str, ...] = MODES                      # frames in which this parameter is meaningful
    sdo_expect: str = "current"                         # pattern compare mode, see patterns.probe_source
    limit_text: str = ""                                # data sheet wording, e.g. "<= 15 ns"; default from direction

    @property
    def limit_label(self) -> str:
        return self.limit_text or f"{'>=' if self.direction == 'min' else '<='} {self.limit_ns} ns"

    def worsen(self, x: float, delta: float) -> float:
        return x - delta if self.direction == "min" else x + delta


class BaselineError(RuntimeError):
    """The probe failed at conservative timing: the setup is broken, not the device."""


@dataclass
class ModeResult:
    mode: str
    at_spec_pass: bool = False
    boundary_pass_ns: float | None = None    # last value that still passed (None: no failure found)
    first_fail_ns: float | None = None
    margin_ns: float | None = None           # headroom to the limit (positive = device better than spec)
    boundary_stable: bool | None = None
    non_monotonic: bool = False
    negative_control_failed: bool = False    # True = the test can see a violation at the far end of the sweep
    sweep: list[tuple[float, bool]] = field(default_factory=list)


@dataclass
class Result:
    spec: ParamSpec
    guard_band_ns: float
    at_spec_value_ns: float
    modes: dict[str, ModeResult]

    @property
    def passed(self) -> bool:
        return all(m.at_spec_pass for m in self.modes.values())


def _probe(runner: Runner, spec: ParamSpec, setup: Setup, mode: str, x: float) -> bool:
    stressed = spec.timing_for(x, setup)
    return runner.run(write=stressed) if mode == "write" else runner.run(read=stressed)


def coarse_points(spec: ParamSpec) -> list[float]:
    sign = 1 if spec.direction == "min" else -1       # +1: x falls as it gets worse
    pts, x = [], spec.baseline_ns
    while sign * (x - spec.end_ns) > 1e-9:
        pts.append(round(x, 6))
        x = spec.worsen(x, spec.coarse_step_ns)
    pts.append(spec.end_ns)
    return pts


def characterize(spec: ParamSpec, runner: Runner, setup: Setup) -> Result:
    # The at-spec point is more severe than the limit by the tester accuracy: a pass there means the
    # device also passes at the exact limit, whatever the actual edge error.
    at_spec = spec.worsen(spec.limit_ns, setup.guard_band_ns)
    modes = spec.modes
    result = Result(spec, setup.guard_band_ns, at_spec, {m: ModeResult(m) for m in modes})
    points = coarse_points(spec)

    # 1. Baseline gate: nominal and conservatively stressed probes must pass, else the setup is suspect.
    if not runner.run():
        raise BaselineError(f"{spec.symbol}: probe fails at all-nominal timing")
    for mode in modes:
        if not _probe(runner, spec, setup, mode, spec.baseline_ns):
            raise BaselineError(f"{spec.symbol}: {mode}-frame probe fails at baseline {spec.baseline_ns} ns")

    for mode in modes:
        r = result.modes[mode]
        # 2. Verdict at the data sheet limit made more severe by the guard band.
        r.at_spec_pass = _probe(runner, spec, setup, mode, at_spec)

        # 3. Coarse sweep (the whole shmoo is kept), then bisect the first failure.
        r.sweep = [(x, _probe(runner, spec, setup, mode, x)) for x in points]
        coarse = list(r.sweep)
        fails = [i for i, (_, ok) in enumerate(coarse) if not ok]
        if fails:
            i = fails[0]
            r.non_monotonic = any(ok for _, ok in coarse[i + 1:])
            if i == 0:
                raise BaselineError(f"{spec.symbol}: {mode}-frame probe fails at the first sweep point")
            good, bad = coarse[i - 1][0], coarse[i][0]
            while abs(good - bad) > setup.bisect_resolution_ns:
                mid = (good + bad) / 2
                ok = _probe(runner, spec, setup, mode, mid)
                r.sweep.append((mid, ok))
                good, bad = (mid, bad) if ok else (good, mid)
            r.boundary_pass_ns, r.first_fail_ns = good, bad
            r.margin_ns = (spec.limit_ns - good) if spec.direction == "min" else (good - spec.limit_ns)
            r.boundary_stable = all(_probe(runner, spec, setup, mode, good)
                                    for _ in range(setup.boundary_repeats))
        # 4. Negative control: the far end of the sweep is a deliberate violation; the device should fail there.
        r.negative_control_failed = not coarse[-1][1]
    return result
