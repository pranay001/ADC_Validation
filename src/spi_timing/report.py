from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from .config import ROOT, Setup
from .sweep import Result


def summarize(result: Result) -> str:
    s = result.spec
    verdict = "PASS" if result.passed else "FAIL"
    lines = [f"{s.symbol} ({s.description}): data sheet limit {s.limit_label}, tested at "
             f"{result.at_spec_value_ns} ns (guard band {result.guard_band_ns} ns, more severe than the limit) "
             f"-> {verdict}"]
    for m in result.modes.values():
        if m.boundary_pass_ns is None:
            found = f"no failure found out to {s.end_ns} ns"
        else:
            flags = ("" if m.boundary_stable else ", UNSTABLE") + (", NON-MONOTONIC" if m.non_monotonic else "")
            found = f"boundary {m.boundary_pass_ns:.2f} ns, margin {m.margin_ns:.2f} ns{flags}"
        ctl = "ok" if m.negative_control_failed else "NOT SENSITIVE at the far end of the sweep"
        spec_ok = "pass" if m.at_spec_pass else "FAIL"
        lines.append(f"  {m.mode:5s}-frame stress: at-spec {spec_ok}; {found}; negative control {ctl}")
    return "\n".join(lines)


def write_report(result: Result, setup: Setup, out_dir: Path = ROOT / "results") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{result.spec.symbol}_{datetime.now():%Y%m%d_%H%M%S}"
    doc = {
        "parameter": result.spec.symbol, "description": result.spec.description,
        "limit": result.spec.limit_label, "at_spec_value_ns": result.at_spec_value_ns,
        "passed": result.passed,
        "conditions": {"vio": setup.vio, "frames_per_point": setup.frames_per_point,
                       "guard_band_ns": setup.guard_band_ns, "module": setup.model,
                       "SIMULATED_NOT_A_MEASUREMENT": setup.simulate},
        "modes": {n: {k: v for k, v in vars(m).items() if k != "sweep"} for n, m in result.modes.items()},
    }
    (out_dir / f"{stem}.json").write_text(json.dumps(doc, indent=2))
    with open(out_dir / f"{stem}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "value_ns", "pass"])
        for n, m in result.modes.items():
            w.writerows((n, f"{x:.4f}", int(ok)) for x, ok in m.sweep)
    return out_dir / f"{stem}.json"
