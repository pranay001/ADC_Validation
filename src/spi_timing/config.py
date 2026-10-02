from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "setup.toml"


@dataclass(frozen=True)
class Setup:
    resource: str
    model: str
    simulate: bool
    pinmap: Path
    compiler: Path
    vio: float
    frames_per_point: int
    guard_band_ns: float
    bisect_resolution_ns: float
    sdo_strobe_ns: float
    boundary_repeats: int
    nominal_period_ns: float
    nominal_sck_fall_ns: float
    nominal_sck_low_ns: float
    nominal_sdi_change_ns: float
    nominal_sdo_strobe_after_fall_ns: float
    nominal_cs_lead_change_ns: float
    nominal_cs_last_change_ns: float


def load_setup(path: Path = DEFAULT_CONFIG) -> Setup:
    with open(path, "rb") as f:
        c = tomllib.load(f)
    n = c["nominal"]
    return Setup(
        resource=c["instrument"]["resource"],
        model=c["instrument"]["model"],
        simulate=c["instrument"]["simulate"],
        pinmap=ROOT / c["instrument"]["pinmap"],
        compiler=Path(c["instrument"]["compiler"]),
        vio=c["levels"]["vio"],
        frames_per_point=c["run"]["frames_per_point"],
        guard_band_ns=c["run"]["guard_band_ns"],
        bisect_resolution_ns=c["run"]["bisect_resolution_ns"],
        sdo_strobe_ns=c["run"]["sdo_strobe_ns"],
        boundary_repeats=c["run"]["boundary_repeats"],
        nominal_period_ns=n["period_ns"],
        nominal_sck_fall_ns=n["sck_fall_ns"],
        nominal_sck_low_ns=n["sck_low_ns"],
        nominal_sdi_change_ns=n["sdi_change_ns"],
        nominal_sdo_strobe_after_fall_ns=n["sdo_strobe_after_fall_ns"],
        nominal_cs_lead_change_ns=n["cs_lead_change_ns"],
        nominal_cs_last_change_ns=n["cs_last_change_ns"],
    )
