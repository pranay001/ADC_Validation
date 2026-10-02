"""C12: interface CRC (SPI_CONFIG_C: CRC_EN_A = 0x1 and CRC_EN_B = 0x2 written in the same frame).

CRC-8 (x^8 + x^2 + x + 1, seed 0xA5) over R/W + address + data. Assumption to confirm on the first bench run: the CRC of
a single-register frame covers the two instruction bytes and the data (read: padding) bytes, as in data sheet Table 22.
  1. CRC enabled: a write with a valid CRC takes effect; the readback returns the data and the device's CRC, which must
     equal the CRC computed over instruction + data.
  2. A write with a corrupted CRC must NOT change the register and must set SPI_STATUS.CRC_ERROR (bit 3).
  3. Enabling only one of the two fields (A = 1 only, B = 2 only) must not enable CRC: plain frames still work.
Bulk transfers with CRC (seed of the following registers) are not covered yet.
"""
from spi_timing.bus import Script, crc8, instruction
from spi_timing.functional import run_or_skip
from spi_timing.registers import CRC_ERROR, SCRATCH_PAD, SPI_CONFIG_C, SPI_STATUS

CRC_ON = 0x62            # CRC_EN_A = 1 (bits 7:6), MB_STRICT = 1 (bit 5), CRC_EN_B = 2 (bits 1:0)
ONLY_A = 0x60            # CRC_EN_A = 1, CRC_EN_B = 0
ONLY_B = 0x22            # CRC_EN_A = 0, CRC_EN_B = 2


def test_crc_enabled(bus):
    s = Script().hw_reset()
    s.write(SPI_CONFIG_C.addr, CRC_ON)                                   # last frame without CRC
    s.write(SCRATCH_PAD.addr, 0xA5, crc=True)
    good = s.read(SCRATCH_PAD.addr, crc=True)
    s.write(SCRATCH_PAD.addr, 0x5A, crc=True, corrupt_crc=True)
    bad_value = s.read(SCRATCH_PAD.addr, crc=True)
    flags = s.read(SPI_STATUS.addr, crc=True)
    s.write(SPI_STATUS.addr, CRC_ERROR, crc=True)
    cleared = s.read(SPI_STATUS.addr, crc=True)
    s.hw_reset()                                                         # CRC back to disabled
    res = run_or_skip(bus, s)

    expected_crc = crc8(instruction(SCRATCH_PAD.addr, read=True).to_bytes(2, "big") + bytes([0xA5]))
    assert res[good].data == [0xA5], f"CRC write/read: read back {res[good].data}"
    assert res[good].crc == expected_crc, f"device CRC 0x{res[good].crc:02X}, expected 0x{expected_crc:02X}"
    assert res[bad_value].data == [0xA5], f"write with corrupted CRC changed SCRATCH_PAD to {res[bad_value].data}"
    assert res[flags].data[0] & CRC_ERROR, f"CRC_ERROR not set (SPI_STATUS = 0x{res[flags].data[0]:02X})"
    assert not res[cleared].data[0] & CRC_ERROR, "CRC_ERROR not cleared by writing 1"


def test_crc_needs_both_enable_fields(bus):
    s = Script().hw_reset()
    results = {}
    for label, config in (("CRC_EN_A only", ONLY_A), ("CRC_EN_B only", ONLY_B)):
        s.write(SPI_CONFIG_C.addr, config)
        s.write(SCRATCH_PAD.addr, 0x3C)                                   # plain frame, no CRC byte
        results[label] = s.read(SCRATCH_PAD.addr)
        s.hw_reset()
    res = run_or_skip(bus, s)

    for label, handle in results.items():
        assert res[handle].value == 0x3C, f"{label} enabled CRC: plain write/read returned 0x{res[handle].value:02X}"
