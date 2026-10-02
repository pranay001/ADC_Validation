"""C3: RESET_FLAG (DEVICE_STATUS bit 5) is set by a reset and cleared by reading DEVICE_STATUS.

Both hardware and software resets must set it; the first read returns 1 and clears it, the second read returns 0.
"""
from spi_timing.bus import SW_RESET_WAIT_NS, Script
from spi_timing.functional import run_or_skip
from spi_timing.registers import DEVICE_STATUS, RESET_FLAG, SPI_CONFIG_A


def test_reset_flag(bus):
    s = Script().hw_reset()
    hw = [s.read(DEVICE_STATUS.addr), s.read(DEVICE_STATUS.addr)]
    s.write(SPI_CONFIG_A.addr, 0x91).wait(SW_RESET_WAIT_NS)
    sw = [s.read(DEVICE_STATUS.addr), s.read(DEVICE_STATUS.addr)]
    res = run_or_skip(bus, s)

    for label, handles in (("hardware", hw), ("software", sw)):
        first, second = (res[h].value & RESET_FLAG for h in handles)
        assert first == RESET_FLAG, f"RESET_FLAG not set after {label} reset"
        assert second == 0, f"RESET_FLAG not cleared by reading DEVICE_STATUS after {label} reset"
