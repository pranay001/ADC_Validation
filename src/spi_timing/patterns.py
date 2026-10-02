"""Pattern text generation and compilation.

Frame layout (SPI mode 3, CS active low; no idle cycles between frames in the timing probe, so every CS edge is
under the control of the time sets):

  LEAD   CS falls here (SCK high)
  FIRST  SCK clock 0 (R/W bit)
  MID    SCK clocks 1..n-2
  LAST   SCK clock n-1; CS rises here, after the SCK rising edge

Each frame kind (PRE = preparatory write, WR = write under test, RD = read under test) has its own four time sets,
TS_<frame>_<role>. A timing test stresses a parameter by reprogramming the edges of the WR or RD sets only; PRE and
everything else stays at conservative nominal timing. The register-access scripts (bus.py) use PRE only.

RESET is held high and CNV low in every vector unless a script says otherwise.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import NamedTuple

SCRATCH_PAD_ADDR = 0x000A
FRAME_CLOCKS = 24            # 1 R/W + 15 address + 8 data
PATTERN_NAME = "scratch_probe"
PIN_ORDER = ("CS", "SCK", "SDI", "SDO", "RESET", "CNV")
ROLES = ("LEAD", "FIRST", "MID", "LAST")
FRAMES = ("PRE", "WR", "RD")
NOM_TIMESET = "TS_NOM"


def timeset_name(frame: str, role: str) -> str:
    return f"TS_{frame}_{role}"


TIMESETS = (NOM_TIMESET,) + tuple(timeset_name(f, r) for f in FRAMES for r in ROLES)

# Alternating-bit values toggle SDI/SDO on every clock; the walking-1 set catches stuck/shifted bits.
DATA_VALUES = (0xA5, 0x5A, 0xFF, 0x00, 0x55, 0xAA) + tuple(1 << i for i in range(8))


class Vec(NamedTuple):
    ts: str
    cs: int
    sck: int
    sdi: int
    sdo: str = "X"            # X ignore, H/L compare, V capture (needs the capture opcode)
    opcode: str = ""
    reset: int = 1            # RESET pin, active low
    cnv: int = 0


def fmt(v: Vec) -> str:
    return f"{v.opcode:<24}{v.ts:<12} {v.cs} {v.sck} {v.sdi} {v.sdo} {v.reset} {v.cnv};"


def render(name: str, vectors: list[Vec]) -> str:
    lines = ["file_format_version 1.0;"] + [f"timeset {t};" for t in TIMESETS] + [""]
    lines += [f"pattern {name} ({', '.join(PIN_ORDER)})", "{"]
    lines += [fmt(v) if isinstance(v, Vec) else v for v in vectors]
    lines += ["}"]
    return "\n".join(lines) + "\n"


def bits(value: int, width: int) -> list[int]:
    return [(value >> (width - 1 - i)) & 1 for i in range(width)]


def probe_frame(kind: str, read: bool, value: int, sdo_expect: str) -> list[Vec]:
    """sdo_expect 'current': compare each data bit in its own cycle (data valid, tDSDO).
    'previous': compare the previous bit in each cycle (data still valid after the falling edge, tHSDO)."""
    sdi = [1 if read else 0] + bits(SCRATCH_PAD_ADDR, 15) + ([0] * 8 if read else bits(value, 8))
    expect: dict[int, str] = {}
    if read:
        data = ["H" if b else "L" for b in bits(value, 8)]
        first_cycle = 16 if sdo_expect == "current" else 17
        count = 8 if sdo_expect == "current" else 7
        expect = {first_cycle + j: data[j] for j in range(count)}
    v = [Vec(timeset_name(kind, "LEAD"), 0, 1, 0)]
    for i in range(FRAME_CLOCKS):
        role = "FIRST" if i == 0 else "LAST" if i == FRAME_CLOCKS - 1 else "MID"
        v.append(Vec(timeset_name(kind, role), 1 if role == "LAST" else 0, 0, sdi[i], expect.get(i, "X")))
    return v


def probe_source(frames: int, values=DATA_VALUES, sdo_expect: str = "current") -> str:
    """Per value: PRE write ~v, WR write v, RD read v. The complementary write guarantees a missed write of v can
    never read back as v. The whole block repeats `frames` times on-instrument."""
    assert sdo_expect in ("current", "previous")
    body: list[Vec] = []
    for v in values:
        body += probe_frame("PRE", False, v ^ 0xFF, sdo_expect)
        body += probe_frame("WR", False, v, sdo_expect)
        body += probe_frame("RD", True, v, sdo_expect)
    body[-1] = body[-1]._replace(opcode="end_loop(loop)")
    vectors: list = [Vec(NOM_TIMESET, 1, 1, 0, opcode=f"set_loop({frames})"), "loop:"]
    vectors += body
    vectors += [Vec(NOM_TIMESET, 1, 1, 0, opcode="halt")]
    return render(PATTERN_NAME, vectors)


def compile_pattern(source: str, build_dir: Path, pinmap: Path, compiler: Path,
                    name: str = PATTERN_NAME) -> Path:
    build_dir.mkdir(parents=True, exist_ok=True)
    src = build_dir / f"{name}.digipatsrc"
    out = build_dir / f"{name}.digipat"
    src.write_text(source)
    r = subprocess.run([str(compiler), "-pinmap", str(pinmap), "-o", str(out), str(src)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"Pattern compile failed:\n{r.stdout}\n{r.stderr}")
    return out
