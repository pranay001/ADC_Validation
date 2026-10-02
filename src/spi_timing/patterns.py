"""Scratch-pad probe pattern: text source generation and compilation.

Frame layout (SPI mode 3, CS active low; no idle cycles between frames, so every CS edge is under the
control of the time sets):

  LEAD   CS falls here (SCK high)
  FIRST  SCK clock 0 (R/W bit)
  MID    SCK clocks 1..22
  LAST   SCK clock 23; CS rises here, after the SCK rising edge

Each of the three frames of a probe (PRE = preparatory write of ~v, WR = write of v, RD = read of v) has its
own four time sets, TS_<frame>_<role>. A test stresses a parameter by reprogramming the edges of the WR or RD
sets only; PRE and everything else stays at conservative nominal timing.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

SCRATCH_PAD_ADDR = 0x000A
FRAME_CLOCKS = 24            # 1 R/W + 15 address + 8 data
PATTERN_NAME = "scratch_probe"
PIN_ORDER = ("CS", "SCK", "SDI", "SDO")
ROLES = ("LEAD", "FIRST", "MID", "LAST")
FRAMES = ("PRE", "WR", "RD")
NOM_TIMESET = "TS_NOM"


def timeset_name(frame: str, role: str) -> str:
    return f"TS_{frame}_{role}"


TIMESETS = (NOM_TIMESET,) + tuple(timeset_name(f, r) for f in FRAMES for r in ROLES)

# Alternating-bit values toggle SDI/SDO on every clock; the walking-1 set catches stuck/shifted bits.
DATA_VALUES = (0xA5, 0x5A, 0xFF, 0x00, 0x55, 0xAA) + tuple(1 << i for i in range(8))

_Vector = tuple[str, str, int, int, int, str]   # opcode, timeset, CS, SCK, SDI, SDO


def _bits(value: int, width: int) -> list[int]:
    return [(value >> (width - 1 - i)) & 1 for i in range(width)]


def _fmt(v: _Vector) -> str:
    opcode, ts, cs, sck, sdi, sdo = v
    return f"{opcode:<18}{ts:<12} {cs} {sck} {sdi} {sdo};"


def _frame(kind: str, read: bool, value: int, sdo_expect: str) -> list[_Vector]:
    """sdo_expect 'current': compare each data bit in its own cycle (data valid, tDSDO).
    'previous': compare the previous bit in each cycle (data still valid after the falling edge, tHSDO)."""
    sdi = [1 if read else 0] + _bits(SCRATCH_PAD_ADDR, 15) + ([0] * 8 if read else _bits(value, 8))
    expect: dict[int, str] = {}
    if read:
        data = ["H" if b else "L" for b in _bits(value, 8)]
        first_cycle = 16 if sdo_expect == "current" else 17
        count = 8 if sdo_expect == "current" else 7
        expect = {first_cycle + j: data[j] for j in range(count)}
    v: list[_Vector] = [("", timeset_name(kind, "LEAD"), 0, 1, 0, "X")]
    for i in range(FRAME_CLOCKS):
        role = "FIRST" if i == 0 else "LAST" if i == FRAME_CLOCKS - 1 else "MID"
        v.append(("", timeset_name(kind, role), 1 if role == "LAST" else 0, 0, sdi[i], expect.get(i, "X")))
    return v


def probe_source(frames: int, values=DATA_VALUES, sdo_expect: str = "current") -> str:
    """Per value: PRE write ~v, WR write v, RD read v. The complementary write guarantees a missed write of v
    can never read back as v. The whole block repeats `frames` times on-instrument."""
    assert sdo_expect in ("current", "previous")
    body: list[_Vector] = []
    for v in values:
        body += _frame("PRE", False, v ^ 0xFF, sdo_expect)
        body += _frame("WR", False, v, sdo_expect)
        body += _frame("RD", True, v, sdo_expect)
    _, ts, cs, sck, sdi, sdo = body[-1]
    body[-1] = ("end_loop(loop)", ts, cs, sck, sdi, sdo)
    lines = ["file_format_version 1.0;"] + [f"timeset {t};" for t in TIMESETS] + [""]
    lines += [f"pattern {PATTERN_NAME} ({', '.join(PIN_ORDER)})", "{"]
    lines += [_fmt((f"set_loop({frames})", NOM_TIMESET, 1, 1, 0, "X")), "loop:"]
    lines += [_fmt(v) for v in body]
    lines += [_fmt(("halt", NOM_TIMESET, 1, 1, 0, "X")), "}"]
    return "\n".join(lines) + "\n"


def compile_pattern(source: str, build_dir: Path, pinmap: Path, compiler: Path) -> Path:
    build_dir.mkdir(parents=True, exist_ok=True)
    src = build_dir / f"{PATTERN_NAME}.digipatsrc"
    out = build_dir / f"{PATTERN_NAME}.digipat"
    src.write_text(source)
    r = subprocess.run([str(compiler), "-pinmap", str(pinmap), "-o", str(out), str(src)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"Pattern compile failed:\n{r.stdout}\n{r.stderr}")
    return out
