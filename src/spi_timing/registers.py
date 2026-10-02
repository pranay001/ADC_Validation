"""AD4691/AD4692 register map (data sheet Table 24, verified against the PDF page image, Rev. 0)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reg:
    name: str
    addr: int                 # for multibyte registers: address of the most significant byte
    nbytes: int = 1
    reset: int = 0
    access: str = "R/W"       # "R" read-only, "R/W" has writable bits
    check_mask: int = 0xFF    # bits compared in the reset-value test (others depend on analog state)
    walk_mask: int = 0        # bits that are safe to write and read back (0 = never written by walking tests)
    ambiguous_reset: str = ""  # non-empty: data sheet contradicts itself; reset check is report-only
    accept: tuple[int, ...] = ()   # alternative acceptable reset values (e.g. AD4691 / AD4692 product id)

    @property
    def mask(self) -> int:
        """Bits compared in the reset-value test, over the whole register width."""
        return self.check_mask if self.nbytes == 1 else (1 << (8 * self.nbytes)) - 1

    @property
    def walk(self) -> int:
        """Bits written and read back by walking tests, over the whole register width."""
        return self.walk_mask


# Registers that must never be written by a walking test:
#   SPI_CONFIG_A (software reset), SPI_CONFIG_C (CRC enable), DEVICE_SETUP (MANUAL_MODE locks out register access,
#   LDO_EN can remove VDD), OSC_EN_REG, STATE_RESET_REG, STREAM_MODE (reserved), GPx_MODE (drive the GP pin).
SPI_CONFIG_A = Reg("SPI_CONFIG_A", 0x0000, reset=0x10)
SPI_CONFIG_B = Reg("SPI_CONFIG_B", 0x0001, reset=0x00)
DEVICE_TYPE = Reg("DEVICE_TYPE", 0x0003, reset=0x07, access="R")
PRODUCT_ID_LSB = Reg("PRODUCT_ID_LSB", 0x0004, reset=0x12, access="R", accept=(0x11, 0x12))  # AD4691 0x11, AD4692 0x12
PRODUCT_ID_MSB = Reg("PRODUCT_ID_MSB", 0x0005, reset=0x00, access="R")
SCRATCH_PAD = Reg("SCRATCH_PAD", 0x000A, reset=0x00, walk_mask=0xFF)
VENDOR_ID_LSB = Reg("VENDOR_ID_LSB", 0x000C, reset=0x56, access="R")
VENDOR_ID_MSB = Reg("VENDOR_ID_MSB", 0x000D, reset=0x04, access="R")
STREAM_MODE = Reg("STREAM_MODE", 0x000E, reset=0x00)
SPI_CONFIG_C = Reg("SPI_CONFIG_C", 0x0010, reset=0x23)
SPI_STATUS = Reg("SPI_STATUS", 0x0011, reset=0x00)
# DEVICE_STATUS: only RESET_FLAG (bit 5) and SPI_ERROR (bit 2) are independent of the analog side.
DEVICE_STATUS = Reg("DEVICE_STATUS", 0x0014, reset=0x20, access="R", check_mask=0x24)
DEVICE_SETUP = Reg("DEVICE_SETUP", 0x0020, reset=0x10)
REF_CTRL = Reg("REF_CTRL", 0x0021, reset=0x10)   # not walked: VREF_SET defines only 0..4, a walk would write 5..7
SEQ_CTRL = Reg("SEQ_CTRL", 0x0022, reset=0x80, walk_mask=0xFF)
OSC_FREQ_REG = Reg("OSC_FREQ_REG", 0x0023, reset=0x00, walk_mask=0x0F)
STD_SEQ_CONFIG = Reg("STD_SEQ_CONFIG", 0x0025, nbytes=2, reset=0x0001, walk_mask=0xFFFF)
OSC_EN_REG = Reg("OSC_EN_REG", 0x0180, reset=0x00)
STATE_RESET_REG = Reg("STATE_RESET_REG", 0x0181, reset=0x01,
                      ambiguous_reset="Table 24 and Table 47 heading say 0x01, Table 47 bit table says 0x0")
ADC_SETUP = Reg("ADC_SETUP", 0x0182, reset=0x00, walk_mask=0x23)
ACC_MASK_1 = Reg("ACC_MASK_1", 0x0184, reset=0xFE, walk_mask=0xFF)
ACC_MASK_2 = Reg("ACC_MASK_2", 0x0185, reset=0xFF, walk_mask=0xFF)
GP0_GP1_MODE = Reg("GP0_GP1_MODE", 0x0196, reset=0x00)
GP2_GP3_MODE = Reg("GP2_GP3_MODE", 0x0197, reset=0x00)
GPIO_READ = Reg("GPIO_READ", 0x01A0, reset=0x00, access="R", check_mask=0x00)  # reflects the GP pin level

CONFIG_IN = tuple(Reg(f"CONFIG_IN{n}", 0x0030 + n, reset=0x08, walk_mask=0x10,
                      ambiguous_reset="Table 24 and Table 44 heading say 0x08, the bit diagram shows 0x00")
                  for n in range(16))
AS_SLOT = tuple(Reg(f"AS_SLOT{n}", 0x0100 + n, reset=0x00, walk_mask=0x0F) for n in range(128))
ACC_DEPTH_IN = tuple(Reg(f"ACC_DEPTH_IN{n}", 0x0186 + n, reset=0x3F, walk_mask=0x3F) for n in range(16))
ACC_STS = (Reg("ACC_STS_FULL_1", 0x01B0, access="R"), Reg("ACC_STS_FULL_2", 0x01B1, access="R"),
           Reg("ACC_STS_OVR_1", 0x01B2, access="R"), Reg("ACC_STS_OVR_2", 0x01B3, access="R"),
           Reg("ACC_STS_SAT_1", 0x01B4, access="R"))
# Table 24 lists ACC_STS_SAT_2 at 0x01BE, which looks like a typo for 0x01B5 (the neighbours are 0x01B0 to 0x01B4).
# It is left out of every check until confirmed on the bench.

SINGLES = (SPI_CONFIG_A, SPI_CONFIG_B, DEVICE_TYPE, PRODUCT_ID_LSB, PRODUCT_ID_MSB, SCRATCH_PAD, VENDOR_ID_LSB,
           VENDOR_ID_MSB, STREAM_MODE, SPI_CONFIG_C, SPI_STATUS, DEVICE_STATUS, DEVICE_SETUP, REF_CTRL, SEQ_CTRL,
           OSC_FREQ_REG, STD_SEQ_CONFIG, OSC_EN_REG, STATE_RESET_REG, ADC_SETUP, ACC_MASK_1, ACC_MASK_2,
           GP0_GP1_MODE, GP2_GP3_MODE, GPIO_READ)

ALL_REGISTERS = SINGLES + CONFIG_IN + AS_SLOT + ACC_DEPTH_IN + ACC_STS
WALKABLE = tuple(r for r in ALL_REGISTERS if r.walk_mask)
READ_ONLY_TARGETS = (DEVICE_TYPE, PRODUCT_ID_LSB, VENDOR_ID_LSB, VENDOR_ID_MSB)   # exclusively read-only bits

# SPI_STATUS bits (Table 35)
NOT_RDY_ERROR, SCK_ERROR, CRC_ERROR, INVALID_WR_ERROR, MB_PARTIAL_ERROR, INVALID_ADDR_ERROR = (
    0x80, 0x10, 0x08, 0x04, 0x02, 0x01)
# DEVICE_STATUS bits (Table 36)
RESET_FLAG, SPI_ERROR = 0x20, 0x04

# Addresses that are undefined in Table 24 (inside gaps of the map and beyond the end of it)
UNDEFINED_ADDRESSES = (0x0002, 0x0007, 0x000B, 0x0040, 0x00FF, 0x0500, 0x7FFF)
HIGHEST_VALID_ADDRESS = 0x02BF
