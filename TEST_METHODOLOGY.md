# AD4691/AD4692 SPI Timing Validation: Test Methodology (as implemented)

Source: AD4691/AD4692 data sheet Rev. 0, Table 3 (SPI timing, all modes except manual mode), Figure 2 (timing voltage levels 0.2/0.8 x VIO), Figure 3 (SPI timing definition diagram).

Decisions from review: NI PXIe-6571 (`digital1`, simulated until the bench is connected); supplies are controlled manually; scratch pad register only (no VENDOR_ID reads, no RESET pin toggling); both instruction and data phase are stressed; VIO = 1.8 V; manual mode (Table 4), tDIS and the CNV-related timings are out of scope.

## 1. Parameters and test files

| Parameter | Limit | What is swept | Frames | File |
|---|---|---|---|---|
| tSCK, SCK period | min 32 ns | SCK period 64 to 20 ns, 50% duty | write, read | `src/tests/test_tsck.py` |
| tSCKL, SCK low time | min 10 ns | low pulse 20 to 4 ns, period fixed at 40 ns | write, read | `src/tests/test_tsckl.py` |
| tSCKH, SCK high time | min 10 ns | high pulse 20 to 4 ns, period fixed at 40 ns | write, read | `src/tests/test_tsckh.py` |
| tSSDI, SDI setup to SCK rise | min 2 ns | SDI change 20 ns to -3 ns before the rising edge | write, read | `src/tests/test_tssdi.py` |
| tHSDI, SDI hold after SCK rise | min 2 ns | SDI change 20 to 0.5 ns after the rising edge | write, read | `src/tests/test_thsdi.py` |
| tSCKCSB, SCK rise to CS rise | min 2 ns | gap 20 ns to -5 ns (CS before the last SCK rise) | write | `src/tests/test_tsckcsb.py` |
| tCSBH, CS high time | min 10 ns | CS high between write and the following read, 20 to 1 ns | write to read | `src/tests/test_tcsbh.py` |
| tEN, CS fall to interface ready | max 15 ns | CS fall to first SCK fall, 40 to 1 ns | write, read | `src/tests/test_ten.py` |
| tDSDO, SCK fall to SDO valid | max 8 ns | SDO strobe 20 ns after SCK fall, moved toward the edge | read | `src/tests/test_tdsdo.py` |
| tHSDO, SDO held after SCK fall | min 2 ns | strobe 0.5 to 12 ns after SCK fall, expecting the previous bit | read | `src/tests/test_thsdo.py` |

Min/max assignment was read from the table layout and cross-checked against Figure 3.

## 2. Common method

### 2.1 Probe transaction (scratch pad 0x000A only)
- **Write frame:** 24 SCK cycles: R/W = 0, 15-bit address, 8 data bits. **Read frame:** R/W = 1, address, then 8 data bits on SDO. SPI mode 3 (SCK idles high, SDI sampled on the rising edge, SDO changes on the falling edge).
- One probe loop covers 14 data values (0xA5, 0x5A, 0xFF, 0x00, 0x55, 0xAA and a walking 1). Per value: a nominal write of the complement (PRE), the write under test (WR), then the readback (RD). The complementary write means a missed write can never read back correctly by chance. The tester compares SDO against the expected value; any mismatch fails the probe. The loop repeats `frames_per_point` (1000) times on the instrument.
- Frames follow each other with no idle cycles, so every CS edge is placed by the time sets: LEAD (CS falls), FIRST, MID, LAST (CS rises after the last SCK rising edge).

### 2.2 One parameter at a time
WR and RD frames each have their own four time sets. A test reprograms the edges of the frame under test; PRE and all other timing stay at conservative nominal timing (100 ns cycle: SCK low 30 ns, SDI change on the SCK fall, first SCK fall 30 ns after CS falls, CS rises 10 ns after the last SCK rise, CS high >= 30 ns). Both instruction and data phase of the stressed frame are stressed. The sweep ranges were checked so that, apart from the parameter under test, every other timing stays at least 2x inside its limit. The only exceptions are inherent to the test: tSCK at the end of its sweep has low/high equal to 10 ns, and tSCKL/tSCKH hold the period at 40 ns, 1.25x the 32 ns minimum.

### 2.3 Three stages per test
1. **Baseline gate:** all-nominal timing and the conservative start of the sweep must pass. If not, the test raises an error (setup problem), not a spec failure.
2. **At-spec verdict (PASS/FAIL):** the parameter is set to the data sheet limit made **more severe by the guard band G (0.5 ns)**, so a pass means the device also passes at the exact limit regardless of tester edge error. Every frame type of the test must pass.
3. **Margin characterization (reported, not asserted):** coarse sweep toward the far end, bisection to 0.1 ns around the first failure, and 3 confirmations of the boundary. Margin = distance from the boundary to the data sheet limit. Non-monotonic behaviour and unstable boundaries are flagged. At the far end of the sweep a **negative control** shows whether the test can see a violation. If the device never fails, the report says "no failure found out to X ns" and "NOT SENSITIVE".

Results go to `results/<parameter>_<timestamp>.json` (verdict, margin, conditions) and `.csv` (full shmoo). With `simulate = true` every result is tagged `SIMULATED_NOT_A_MEASUREMENT`.

### 2.4 Instrument notes
Pins CS, SCK, SDI, SDO on a PXIe-6571. SCK uses return-to-high drive, CS and SDI non-return, SDO compare-only with VOL/VOH = 0.2/0.8 x VIO. Text patterns are generated by Python and compiled with NI's `DigitalPatternCompiler.exe`. Edges are programmed in ns and snapped to the module resolution (about 39 ps); the 0.5 ns guard band is a placeholder for the module's edge placement accuracy. Cable and fixture deskew is not yet applied, so output-timing results (tDSDO, tHSDO) are only meaningful once the edges are referenced to the DUT pins and the SDO load is close to the 20 pF in the data sheet.

## 3. Per-parameter notes

- **tSCK / tSCKL / tSCKH:** SDI changes on the SCK fall, so SDI setup equals the low time and hold equals the high time, both above 4 ns throughout. SDO is strobed 12 ns after the fall (tDSDO max is 8 ns), so output delay cannot be mistaken for a clock-width failure. The last clock cycle is lengthened so CS rises at least 10 ns after the last SCK edge, without changing the stressed high/low times.
- **tSSDI / tHSDI:** values 0x55/0xAA make every data bit toggle. For hold, the SCK rising edge sits 0.4 ns before the end of the cycle and SDI changes early in the next cycle, which limits the sweep to holds >= 0.4 ns (it ends at 0.5 ns, so the negative control may not see a violation). Hold of bit k is set by the SDI timing of cycle k+1, so the last cycle stays nominal and 22 of the 23 hold events are stressed.
- **tSCKCSB:** write frame only. When CS rises before the last SCK edge the last bit is not clocked, the partial register write is ignored, and the readback shows the old value. The read frame cannot show this parameter because the last SDO bit is strobed before CS rises.
- **tCSBH:** the CS rising edge of the write frame and the CS falling edge of the read frame that follows it directly define the high time. Only the write-to-read boundary is stressed.
- **tEN:** read as CS falling edge to first SCK falling edge (Figure 3). The device must work when SCK starts 15 ns after CS.
- **tDSDO:** the earliest strobe offset at which every bit reads correctly is the measured data-valid delay.
- **tHSDO:** the pattern expects the previous bit (cycles 17 to 23); the latest strobe offset at which the previous bit is still valid is the measured hold.

## 4. Running

```
uv sync
uv run pytest -s                       # all ten
uv run pytest -s src/tests/test_tsck.py    # one parameter
```

Before real measurements: set `simulate = false` in `config/setup.toml`, put the real channel assignment in `digital/AD469x.pinmap`, confirm VIO matches the supply, replace the guard band with the module's edge placement accuracy, and apply fixture deskew.

## 5. Known limits
- The simulated instrument has no DUT, so every probe passes; passing there only shows that patterns compile and all edge placements are valid.
- Bench results at ambient temperature do not prove the full-temperature data sheet limits.
- The device may tolerate more than the specification; in that case the report gives a lower bound on margin rather than a boundary.
- tHSDI cannot go below about 0.4 ns hold with the present edge placement.

## 6. Functional register tests (group C), `src/tests/test_c*.py`

These use registers beyond the scratch pad, hardware reset, and CRC. Frames are built by `src/spi_timing/bus.py` (`Script` of write/read/reset/wait operations, one pattern per script, SDO captured with a serial capture waveform), the register map is in `src/spi_timing/registers.py` (Table 24, checked against the PDF page image). Nominal timing everywhere; expected values are checked in Python after the burst.

| Test | Checks |
|---|---|
| `test_c01_reset_values` | every defined register read after hardware reset vs Table 24 (PRODUCT_ID accepts AD4691 0x11 / AD4692 0x12; CONFIG_INn and STATE_RESET_REG are report-only because the data sheet contradicts itself) |
| `test_c02_software_reset` | LSB-only or MSB-only SW_RST write does nothing; both bits reset all registers except SPI_CONFIG_A, bits self-clear, RESET_FLAG set |
| `test_c03_reset_flag` | RESET_FLAG set by hardware and software reset, cleared by reading DEVICE_STATUS |
| `test_c04_register_rw` | walking values per register, then a distinct value in every writable register (including the 128 AS_SLOTn), then the complement; registers that change device behaviour are never written |
| `test_c05_readonly_protection` | writes to read-only registers ignored, INVALID_WR_ERROR set and clearable |
| `test_c06_invalid_address` | undefined addresses (read and write) set INVALID_ADDR_ERROR; 0x02BF does not |
| `test_c07_sck_count_error` | 7, 12, 15 data clocks set SCK_ERROR; the 7-clock write is ignored |
| `test_c08_multibyte_partial` | one-byte read/write of STD_SEQ_CONFIG sets MB_PARTIAL_ERROR, partial write ignored, full 16-bit write works |
| `test_c09_not_ready_error` | frame 20 us after the RESET edge sets NOT_RDY_ERROR and is ignored |
| `test_c10_bulk_autodecrement` | 16-byte bulk read and write across ACC_DEPTH_IN15..0 |
| `test_c11_bulk_direct_address` | several instruction+data groups in one frame with INST_MODE = 1, then back to autodecrement |
| `test_c12_crc` | valid CRC accepted and device CRC correct; corrupted CRC ignored and CRC_ERROR set; CRC_EN_A or CRC_EN_B alone does not enable CRC |

With `simulate = true` these tests compile, load and burst their patterns, then skip: there is no DUT behind SDO, so no result is evaluated. `src/tests/test_bus_encoding.py` checks the CRC-8 and frame encoding as pure functions. Assumptions to confirm on the first bench run: CRC coverage of single-register frames (instruction + data), that SPI_STATUS survives a hardware reset long enough to be read in C9, and the data sheet items listed in the report (CONFIG_INn / STATE_RESET_REG reset values, ACC_STS_SAT_2 address 0x01BE). The pin map now also contains RESET, CNV and GP0 (random channels, LFCSP has one GP pin); the timing patterns drive RESET high and CNV low.
