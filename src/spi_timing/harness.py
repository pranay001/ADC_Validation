"""Shared body of every timing test file."""
from __future__ import annotations

from .config import Setup
from .instrument import Probe
from .report import summarize, write_report
from .sweep import ParamSpec, characterize


def run_timing_test(spec: ParamSpec, probe: Probe, setup: Setup) -> None:
    result = characterize(spec, probe, setup)
    print("\n" + summarize(result))
    print("report:", write_report(result, setup))
    assert result.passed, summarize(result)
