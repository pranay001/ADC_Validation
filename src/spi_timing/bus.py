"""Register access scripts: build SPI frames, run them on the instrument and return what the DUT sent on SDO.

A Script is an ordered list of operations (frames, hardware resets, waits). `RegisterBus.run` turns it into a
pattern (nominal timing everywhere), compiles and bursts it once, and fetches the SDO data captured during the
read regions of the frames. All expected values are decided by the test after the run; the pattern has no compare.

Frame format (data sheet "Register Access"): 16-bit instruction = R/W bit (1 = read) + 15-bit address, then
REG_DATA bytes. In autodecrement mode (default) a frame with n bytes accesses addr, addr-1, ... In direct-address
mode (SPI_CONFIG_B.INST_MODE = 1) every REG_DATA byte group is preceded by its own instruction. With CRC enabled
each register's REG_DATA is followed by a CRC-8 byte (x^8 + x^2 + x + 1, seed 0xA5, first register of a frame).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import nidigital

from .config import ROOT, Setup
from .instrument import open_session
from .patterns import NOM_TIMESET, Vec, bits, compile_pattern, render, timeset_name

CAPTURE_WAVEFORM = "sdo_wf"
FRAME_KIND = "PRE"            # nominal time sets
PERIOD_NS = 100.0
HW_RESET_LOW_NS = 1_000.0     # data sheet tRESETL min 10 ns
HW_RESET_WAIT_NS = 500_000.0  # data sheet tHWR 300 us typical
SW_RESET_WAIT_NS = 500_000.0  # data sheet tSWR 300 us typical


def crc8(data: bytes, seed: int = 0xA5) -> int:
    """CRC-8, polynomial x^8 + x^2 + x + 1 (0x07), MSB first, no final XOR."""
    crc = seed
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def instruction(addr: int, read: bool) -> int:
    assert 0 <= addr < 0x8000
    return (0x8000 if read else 0) | addr


def to_bytes(value: int | bytes | list[int], nbytes: int = 1) -> bytes:
    if isinstance(value, int):
        return value.to_bytes(nbytes, "big")
    return bytes(value)


@dataclass
class _Unit:
    """One instruction + REG_DATA group inside a frame."""
    sdi: list[int]
    capture: list[bool]
    reads: list[int] = field(default_factory=list)       # indexes into Script.read_specs


@dataclass(frozen=True)
class ReadSpec:
    nbytes: int
    crc: bool


@dataclass(frozen=True)
class ReadResult:
    data: list[int]
    crc: int | None

    @property
    def value(self) -> int:
        """Data bytes as one big-endian integer (most significant byte first)."""
        return int.from_bytes(bytes(self.data), "big")


def encode_write(addr: int, data: bytes, crc: bool = False, corrupt_crc: bool = False) -> _Unit:
    instr = instruction(addr, read=False).to_bytes(2, "big")
    sdi = bits(int.from_bytes(instr + data, "big"), 8 * (2 + len(data)))
    if crc:
        check = crc8(instr + data) ^ (0xFF if corrupt_crc else 0)
        sdi += bits(check, 8)
    return _Unit(sdi, [False] * len(sdi))


def encode_read(addr: int, nbytes: int, crc: bool, read_index: int, corrupt_crc: bool = False) -> _Unit:
    instr = instruction(addr, read=True).to_bytes(2, "big")
    sdi = bits(int.from_bytes(instr, "big"), 16) + [0] * (8 * nbytes)
    capture = [False] * 16 + [True] * (8 * nbytes)
    if crc:
        check = crc8(instr + bytes(nbytes)) ^ (0xFF if corrupt_crc else 0)
        sdi += bits(check, 8)
        capture += [True] * 8
    return _Unit(sdi, capture, [read_index])


class Script:
    def __init__(self) -> None:
        self.ops: list[tuple] = []
        self.read_specs: list[ReadSpec] = []

    # --- operations -------------------------------------------------------------------------------------
    def hw_reset(self, low_ns: float = HW_RESET_LOW_NS, wait_ns: float = HW_RESET_WAIT_NS) -> "Script":
        self.ops.append(("reset", low_ns, wait_ns))
        return self

    def wait(self, ns: float) -> "Script":
        self.ops.append(("wait", ns))
        return self

    def write(self, addr: int, data: int | bytes | list[int], nbytes: int = 1, crc: bool = False,
              corrupt_crc: bool = False) -> "Script":
        self.ops.append(("frame", [encode_write(addr, to_bytes(data, nbytes), crc, corrupt_crc)]))
        return self

    def read(self, addr: int, nbytes: int = 1, crc: bool = False, corrupt_crc: bool = False) -> int:
        """Append a read frame; returns the handle used to look the result up in RunResult.reads."""
        index = len(self.read_specs)
        self.read_specs.append(ReadSpec(nbytes, crc))
        self.ops.append(("frame", [encode_read(addr, nbytes, crc, index, corrupt_crc)]))
        return index

    def multi(self, *units: tuple) -> list[int]:
        """One CS frame with several instruction+data groups (direct-address mode).
        units: ("w", addr, data_bytes) or ("r", addr, nbytes). Returns read handles in order."""
        encoded, handles = [], []
        for u in units:
            if u[0] == "w":
                encoded.append(encode_write(u[1], to_bytes(u[2])))
            else:
                index = len(self.read_specs)
                self.read_specs.append(ReadSpec(u[2], False))
                encoded.append(encode_read(u[1], u[2], False, index))
                handles.append(index)
        self.ops.append(("frame", encoded))
        return handles

    def bulk_read(self, addr: int, nbytes: int) -> int:
        """Autodecrement bulk read: one frame returning addr, addr-1, ..., addr-nbytes+1."""
        return self.read(addr, nbytes)

    def raw(self, sdi_bits: list[int]) -> "Script":
        """Frame with an arbitrary number of SCK clocks and no capture (SCK count error tests)."""
        self.ops.append(("frame", [_Unit(list(sdi_bits), [False] * len(sdi_bits))]))
        return self

    def raw_write(self, addr: int, data_bits: list[int]) -> "Script":
        """Write instruction followed by exactly `data_bits` clocks of data phase (any length)."""
        return self.raw(bits(instruction(addr, read=False), 16) + list(data_bits))


# --- pattern generation -----------------------------------------------------------------------------------
def _frame_vectors(units: list[_Unit]) -> list[Vec]:
    sdi = [b for u in units for b in u.sdi]
    cap = [c for u in units for c in u.capture]
    n = len(sdi)
    has_cap = any(cap)
    vectors = [Vec(timeset_name(FRAME_KIND, "LEAD"), 0, 1, 0, opcode="capture_start(" + CAPTURE_WAVEFORM + ")" if has_cap else "")]
    for i in range(n):
        role = "LAST" if i == n - 1 else "FIRST" if i == 0 else "MID"
        vectors.append(Vec(timeset_name(FRAME_KIND, role), 1 if role == "LAST" else 0, 0, sdi[i],
                           "V" if cap[i] else "X", "capture" if cap[i] else ""))
    vectors.append(Vec(NOM_TIMESET, 1, 1, 0, opcode="capture_stop" if has_cap else ""))
    return vectors


def _repeat(ns: float, reset: int = 1) -> Vec:
    count = max(1, round(ns / PERIOD_NS))
    return Vec(NOM_TIMESET, 1, 1, 0, opcode=f"repeat({count})", reset=reset)


def script_source(script: Script, name: str) -> str:
    vectors: list = [Vec(NOM_TIMESET, 1, 1, 0)]
    for op in script.ops:
        if op[0] == "frame":
            vectors += _frame_vectors(op[1])
        elif op[0] == "reset":
            vectors += [_repeat(op[1], reset=0), _repeat(op[2])]
        elif op[0] == "wait":
            vectors.append(_repeat(op[1]))
    vectors.append(Vec(NOM_TIMESET, 1, 1, 0, opcode="halt"))
    return render(name, vectors)


# --- execution ---------------------------------------------------------------------------------------------
@dataclass
class RunResult:
    reads: list[ReadResult]

    def __getitem__(self, handle: int) -> ReadResult:
        return self.reads[handle]


class RegisterBus:
    def __init__(self, setup: Setup, name: str = "bus"):
        self.setup = setup
        self.build_dir = ROOT / "build" / name
        self.session: nidigital.Session | None = None
        self._runs = 0

    @property
    def simulated(self) -> bool:
        return self.setup.simulate

    def open(self) -> "RegisterBus":
        self.session = open_session(self.setup)
        return self

    def close(self) -> None:
        if self.session is not None:
            self.session.close()
            self.session = None

    def run(self, script: Script) -> RunResult:
        assert self.session is not None, "call open() first"
        self._runs += 1
        name = f"script_{self._runs}"
        source = script_source(script, name)
        pattern = compile_pattern(source, self.build_dir, self.setup.pinmap, self.setup.compiler, name=name)
        self.session.unload_all_patterns()
        self.session.pins["SDO"].create_capture_waveform_serial(CAPTURE_WAVEFORM, 8, nidigital.BitOrder.MSB)
        self.session.load_pattern(str(pattern))
        self.session.burst_pattern(name, timeout=_timeout(script))
        total = sum(s.nbytes + (1 if s.crc else 0) for s in script.read_specs)
        samples = [int(x) & 0xFF for x in self.session.fetch_capture_waveform(CAPTURE_WAVEFORM, total)[0]] if total else []
        reads, pos = [], 0
        for spec in script.read_specs:
            data = samples[pos:pos + spec.nbytes]
            pos += spec.nbytes
            crc = None
            if spec.crc:
                crc, pos = samples[pos], pos + 1
            reads.append(ReadResult(data, crc))
        return RunResult(reads)


def _timeout(script: Script):
    import hightime
    return hightime.timedelta(seconds=60 + len(script.ops) * 0.01)
