"""C2: software reset through SPI_CONFIG_A (data sheet "Software Reset").

SW_RST_MSB and SW_RST_LSB must both be 1 in the same write frame. Writing only one of them must not reset the device.
After a real software reset all registers return to their defaults except SPI_CONFIG_A, whose reset bits self-clear,
and RESET_FLAG in DEVICE_STATUS is set.
"""
from spi_timing.bus import SW_RESET_WAIT_NS, Script
from spi_timing.functional import hexs, run_or_skip
from spi_timing.registers import (ACC_MASK_1, DEVICE_STATUS, RESET_FLAG, SCRATCH_PAD, SPI_CONFIG_A)

LSB_ONLY, MSB_ONLY, BOTH = 0x11, 0x90, 0x91       # bit 4 is the reserved bit that reads 1 after reset


def test_software_reset(bus):
    s = Script().hw_reset()
    s.read(DEVICE_STATUS.addr)                                   # clears RESET_FLAG
    s.write(SCRATCH_PAD.addr, 0xA5).write(ACC_MASK_1.addr, 0x55)
    s.write(SPI_CONFIG_A.addr, LSB_ONLY)
    lsb = [s.read(SCRATCH_PAD.addr), s.read(ACC_MASK_1.addr)]
    s.write(SPI_CONFIG_A.addr, MSB_ONLY)
    msb = [s.read(SCRATCH_PAD.addr), s.read(ACC_MASK_1.addr)]
    s.write(SPI_CONFIG_A.addr, BOTH).wait(SW_RESET_WAIT_NS)
    after = [s.read(SCRATCH_PAD.addr), s.read(ACC_MASK_1.addr), s.read(SPI_CONFIG_A.addr),
             s.read(DEVICE_STATUS.addr)]
    res = run_or_skip(bus, s)

    assert [res[h].value for h in lsb] == [0xA5, 0x55], f"LSB-only write must not reset: {hexs(res[h].value for h in lsb)}"
    assert [res[h].value for h in msb] == [0xA5, 0x55], f"MSB-only write must not reset: {hexs(res[h].value for h in msb)}"
    scratch, acc_mask, config_a, dev_status = (res[h].value for h in after)
    assert scratch == SCRATCH_PAD.reset, f"SCRATCH_PAD not reset: 0x{scratch:02X}"
    assert acc_mask == ACC_MASK_1.reset, f"ACC_MASK_1 not reset: 0x{acc_mask:02X}"
    assert config_a & 0x81 == 0, f"SW_RST bits did not self-clear: SPI_CONFIG_A = 0x{config_a:02X}"
    assert dev_status & RESET_FLAG, f"RESET_FLAG not set after software reset: DEVICE_STATUS = 0x{dev_status:02X}"
