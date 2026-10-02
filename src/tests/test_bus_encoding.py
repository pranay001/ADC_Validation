"""Pure-function checks of the frame encoding used by the register tests (no instrument involved)."""
from spi_timing.bus import Script, crc8, encode_read, encode_write, instruction, script_source


def test_crc8_known_values():
    assert crc8(b"") == 0xA5                       # seed only
    assert crc8(b"\x00", seed=0x00) == 0x00
    assert crc8(b"\x01", seed=0x00) == 0x07        # polynomial x^8 + x^2 + x + 1
    assert crc8(b"\x80", seed=0x00) == 0x89
    assert crc8(b"123456789", seed=0x00) == 0xF4   # standard CRC-8 (poly 0x07) check value


def test_instruction_word():
    assert instruction(0x000A, read=False) == 0x000A
    assert instruction(0x000A, read=True) == 0x800A
    assert instruction(0x02BF, read=True) == 0x82BF


def test_write_frame_bits():
    u = encode_write(0x000A, b"\xA5")
    assert len(u.sdi) == 24 and not any(u.capture)
    assert u.sdi[:16] == [0] * 12 + [1, 0, 1, 0] and u.sdi[16:] == [1, 0, 1, 0, 0, 1, 0, 1]


def test_read_frame_captures_only_the_data_phase():
    u = encode_read(0x000A, 1, crc=False, read_index=0)
    assert u.sdi[0] == 1 and len(u.sdi) == 24
    assert u.capture == [False] * 16 + [True] * 8


def test_crc_frames_append_a_crc_byte():
    w = encode_write(0x000A, b"\xA5", crc=True)
    assert len(w.sdi) == 32
    expected = crc8(bytes([0x00, 0x0A, 0xA5]))
    assert w.sdi[24:] == [(expected >> (7 - i)) & 1 for i in range(8)]
    bad = encode_write(0x000A, b"\xA5", crc=True, corrupt_crc=True)
    assert bad.sdi[:24] == w.sdi[:24] and bad.sdi[24:] != w.sdi[24:]
    r = encode_read(0x000A, 1, crc=True, read_index=0)
    assert len(r.sdi) == 32 and r.capture == [False] * 16 + [True] * 16


def test_pattern_source_structure():
    s = Script().hw_reset().write(0x000A, 0x5A)
    h = s.read(0x000A)
    text = script_source(s, "demo")
    assert "capture_start(sdo_wf)" in text and "capture_stop" in text and text.count("capture ") == 8
    assert "repeat(5000)" in text and h == 0
    assert text.rstrip().endswith("}") and "halt" in text
