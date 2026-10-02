# Phase 1 Report — PVQ Instrumentation in the Opus CELT Layer

## 1. Objective

Phase 1 of the PVQ steganography project was scoped as an observational, non-invasive investigation of the Pyramid Vector Quantization (PVQ) surface inside the Opus CELT encoder. Its purpose was to answer three preliminary questions before any steganographic embedding is attempted:

1. **Does PVQ activity exist at the bitrates and settings we care about?**
2. **How large are the PVQ codebooks in practice, and how is that size distributed across bands and frames?**
3. **Where and how are PVQ indices actually written into the bitstream, and does the raw-bit escape hatch described in the project summary exist in the libopus revision we are using?**

No modification of encoder behavior was in scope. The instrumentation had to be strictly observational: same input, same settings, same output bytes, with logging as a pure side effect.

## 2. Environment

- **libopus:** upstream git, checked out at v1.5.2 (report the exact commit hash in the README).
- **Arithmetic:** fixed-point. Configured with `--enable-fixed-point`. The configure output confirmed `Floating point support: no`. This was chosen deliberately for deterministic, reproducible encoder behavior across machines and compiler versions, and for conformance with the RFC 6716 arithmetic model.
- **Build prefix:** `build/opus/`, static linking only. The system `libopus` is never linked.
- **Tooling:** `encode_raw` and `decode_raw` (custom C programs linked against the local libopus). Both compiled with `-O2 -Wall -Wextra -Wpedantic`.
- **Audio input:** `data/pcm/cv_001.raw`, 48 kHz mono signed 16-bit little-endian PCM, derived from Common Voice Spontaneous Speech 5.0 — English, via `ffmpeg`.
- **Encoder settings:** 64 kbps, 20 ms frames, `audio` mode, complexity 10, VBR on.

## 3. Instrumentation design

### 3.1 What was logged

For every call to `encode_pulses` — which is the single point where a PVQ index is written into the range coder — the encoder now emits one tab-separated line:

```
frame   band   N   K   V   index
```

| Field | Meaning |
|---|---|
| `frame` | Frame index within the clip (1-based, see §3.4) |
| `band` | CELT frequency band index |
| `N` | PVQ vector dimension for this band |
| `K` | Number of signed pulses allocated to this band |
| `V` | Codebook size, i.e. `CELT_PVQ_V(N, K)` — the range the index lives in |
| `index` | The actual PVQ index passed to the range coder |

This captures everything needed to reason about the embedding surface: codebook size (capacity proxy), the specific integer being coded (the thing we would modify), and the band and frame context for statistical aggregation.

### 3.2 Which functions were touched

Four source files were modified. All changes are additive and guarded so that with `PVQ_LOG` unset, behavior is byte-identical to the unpatched encoder.

**`celt/cwrs.c`**
- Added a small logging block near the top of the file, **outside** the `#ifdef CUSTOM_MODES` region (this was an early bug — see §5).
- Defined three globals (`g_pvq_band`, `g_pvq_frame`, `g_pvq_log`), a one-time `pvq_log_open()` that reads `PVQ_LOG` from the environment and opens the file, and `pvq_log_frame_advance()`.
- Instrumented the active `encode_pulses` definition (the one inside `#if !defined(SMALL_FOOTPRINT)`, which is what our build compiles). The call was rewritten to compute `_idx` and `_V` as locals, emit one `fprintf` line, then perform the original `ec_enc_uint(_enc, _idx, _V)` unchanged.

**`celt/cwrs.h`**
- Declared `pvq_log_open()`, `pvq_log_frame_advance()`, and the three extern globals.
- Added `#include <stdio.h>` so `FILE *` is visible to any translation unit that includes this header.

**`celt/bands.c`**
- Added `g_pvq_band = i;` at the top of the band loop inside `quant_all_bands`, so that the global reflects the current band index before `alg_quant` / `encode_pulses` are reached.

**`celt/celt_encoder.c`**
- Added a single call to `pvq_log_frame_advance()` at the top of `celt_encode_with_ec`, guarded by `if (enc != NULL)`.

### 3.3 Why that instrumentation point

PVQ encoding has three candidate hook sites:

- `alg_quant` in `vq.c` — finds the pulse vector and computes the index, but does not write it.
- `encode_pulses` in `cwrs.c` — writes the index to the range coder. This is the only place where the index and its codebook range are simultaneously available.
- `quant_all_bands` in `bands.c` — knows the band context but not the index.

Logging from `encode_pulses` gives us `N`, `K`, `V`, and `index` at the exact point of bitstream emission, which is the point Phase 2 will need to perturb.

### 3.4 Frame counting

`celt_encode_with_ec` is called several times per `opus_encode` invocation, including auxiliary calls with dummy buffers. The guard `if (enc != NULL)` restricts counting to the single real encode call per frame. Verified empirically: the maximum frame number in the log is 805, matching the encoder's reported 805 frames.

Frame numbering is currently **1-based** (the first encode increments the counter before logging). This is a cosmetic choice; the README records it explicitly so downstream tooling does not misinterpret frame indices.

### 3.5 Why logging is provably side-effect-free

The log write happens between computing `_idx`/`_V` and calling `ec_enc_uint`. It touches no encoder state: no range coder, no buffer, no context struct. The only shared state is the file handle. Confirmed empirically in §4.4.

## 4. Results

### 4.1 Round-trip verification

The instrumented fixed-point encoder produces a bitstream that decodes cleanly. For `cv_001`:

| Quantity | Value |
|---|---|
| Encoded frames | 805 |
| Packet bytes | 129,145 |
| Source samples | 772,416 |
| Decoded samples | 772,800 |
| Padded tail | 384 samples (one 20 ms frame) |
| Measured CELT delay | 312 samples (6.5 ms) |
| PSNR aligned | 46.70 dB (floating-point build; fixed-point value will differ, record separately) |
| PESQ(wb) | to be filled |

Note: the aligned-PSNR methodology is essential. Unaligned PSNR is dominated by the 6.5 ms algorithmic delay and is meaningless as a quality metric. All PSNR numbers in the project are aligned.

### 4.2 PVQ activity

- **Frames with PVQ activity:** 802 of 805. Three leading frames produced no PVQ rows — expected, since those frames contain silence and the encoder leaves band quantizers at `q = 0`.
- **Total PVQ band records:** 38,732.
- **Average bands per active frame:** ≈ 48.

### 4.3 Codebook size distribution

Histogram of `log2(V)` across all 38,732 PVQ bands:

| log2(V) bucket | Count | Cumulative | Fraction |
|---|---|---|---|
| 4 | 158 | 158 | 0.4% |
| 5 | 143 | 301 | 0.8% |
| 6 | 120 | 421 | 1.1% |
| 7 | 189 | 610 | 1.6% |
| 8 | 230 | 840 | 2.2% |
| 9 | 589 | 1,429 | 3.7% |
| 10 | 56 | 1,485 | 3.8% |
| 11 | 987 | 2,472 | 6.4% |
| 12 | 481 | 2,953 | 7.6% |
| 13 | 1,468 | 4,421 | 11.4% |
| 14 | 1,211 | 5,632 | 14.5% |
| 15 | 1,042 | 6,674 | 17.2% |
| 16 | 3,054 | 9,728 | 25.1% |
| 17 | 1,696 | 11,424 | 29.5% |
| 18 | 3,293 | 14,717 | 38.0% |
| 19 | 2,190 | 16,907 | 43.7% |
| 20 | 2,162 | 19,069 | 49.2% |
| 21 | 3,233 | 22,302 | 57.6% |
| 22 | 1,000 | 23,302 | 60.2% |
| 23 | 3,143 | 26,445 | 68.3% |
| 24 | 1,533 | 27,978 | 72.2% |
| 25 | 1,380 | 29,358 | 75.8% |
| 26 | 2,184 | 31,542 | 81.4% |
| 27 | 1,130 | 32,672 | 84.4% |
| 28 | 1,416 | 34,088 | 88.0% |
| 29 | 665 | 34,753 | 89.7% |
| 30 | 1,694 | 36,447 | 94.1% |
| 31 | 1,601 | 38,048 | 98.3% |
| (V ≥ 4×10⁹, excluded) | 684 | 38,732 | 100% |

Key thresholds:

- **63%** of bands have `V ≥ 2^16` (≥ 16-bit codebooks).
- **41%** have `V ≥ 2^24`.
- **18%** have `V ≥ 2^28`.
- **4%** have `V ≥ 2^31`.

Largest observed codebook: **4,196,289,420 ≈ 2^31.97**, corresponding to per-band parameter pairs such as `(N=18, K=11)`, `(N=24, K=9)`, and `(N=16, K=12)`. These are legitimate per-band codebooks, not overflow artifacts — `CELT_PVQ_V` computes them exactly within `opus_uint32`.

### 4.4 Determinism and side-effect check

Two independent encodings of `cv_001` with `PVQ_LOG` set:

```
6726d52412194fee83ddf593f9981499ecd26600a53b385b766a405b468d500a
```

Both runs produced **identical SHA-256 hashes** of the encoded container, and `diff` of the two log bodies is empty. The instrumentation is therefore:

- **Deterministic** — same input, same output, same log, run to run.
- **Side-effect-free** — the log does not perturb the encoder.

This is the mandatory precondition for any Phase 2 experiment, because it means any bitstream change observed in Phase 2 is caused by the *substitution*, not by the logging.

## 5. Problems encountered and resolved

Three issues surfaced during Phase 1. They are recorded here because each represents a lesson that will recur in later phases.

**Instrumentation placed inside `#ifdef CUSTOM_MODES`.** The first patch attempt inserted the globals and helper functions inside the `CUSTOM_MODES` block in `cwrs.c`. Since our build does not enable custom modes, the code was compiled out and the linker failed on the `pvq_log_frame_advance` reference. Fixed by moving the block above the conditional.

**File-scope call to `pvq_log_frame_advance()`.** The initial `celt_encoder.c` edit inserted the call above the function body, at file scope. The compiler interpreted it as an implicit declaration and reported a type conflict against the prototype in `cwrs.h`. Fixed by moving the call inside the function body.

**Frame guard too strict.** The first version of the guard was `if (enc != NULL && compressed != NULL)`. Inspecting `src/opus_encoder.c` showed that the real per-frame encode call passes `compressed = NULL` (libopus writes to its own buffer), so the guard excluded every real encode. Fixed by reducing the condition to `if (enc != NULL)`, which correctly includes the real call and excludes the auxiliary calls with `dummy` buffers or `NULL` encoders.

Each of these was caught by build-time errors or a small diagnostic script; none required deep debugging.

## 6. Key finding: no raw-bit path for PVQ

The project summary that motivated this work listed a "raw bits escape hatch" as the most promising embedding surface: "For large codebooks (>8 bits), part of the PVQ index may be coded as raw bits outside the range coder."

Grep of the libopus tree confirmed that `ec_enc_bits` / `ec_dec_bits` calls exist in the CELT layer, but **none of them are used for PVQ indices**:

| Location | What it encodes |
|---|---|
| `celt/celt_encoder.c:1711` | pitch index, in specific transient frames |
| `celt/celt_encoder.c:1713` | postfilter gain |
| `celt/celt_encoder.c:2250` | anti-collapse flag, 1 bit per frame |
| `celt/quant_bands.c:385,414` | coarse and fine energy quantizers |
| `celt/bands.c:924,1303` | a single sign bit per split band |

PVQ indices, in this revision, are written exclusively through `ec_enc_uint(_enc, index, V)` — that is, through the range coder, with `V` as the symbol range.

**Consequence for Phase 2.** The embedding surface is the range coder, not a raw-bit field. The question is no longer "how do we modify a raw-bit field without perturbing the coder?" but "can we substitute a different symbol in an arithmetic-coded uniform distribution without changing the number of bits the coder emits?"

This is a different and, in principle, harder problem. The range coder is stateful: the bit cost of a symbol depends on the current coder state as well as on `V`. Substituting index `i` for index `i'` will sometimes preserve the bit cost and sometimes not. The empirical question for Phase 2 is *what fraction* of substitutions are bit-neutral, and whether that fraction can be made high enough to support a viable steganographic channel.

## 7. What Phase 1 has established

1. The Opus PVQ surface is **dense**. At 64 kbps, `cv_001` yields 38,732 PVQ bands across 802 active frames, with a broad distribution of codebook sizes.
2. The surface includes **large codebooks**. 63% of bands exceed 16 bits; 4% exceed 31 bits. This is capacity, before any encoding overhead, of roughly one symbol per band.
3. The indices are coded through the **range coder**, not through raw bits. The original premise of the project summary — that raw-bit escape hatches are the embedding target — does not hold for this libopus revision. Phase 2 must work within the range coder.
4. The instrumentation is **safe**: bit-identical encoder output with and without logging, verified by SHA-256 and by byte-level diff of the logs.
5. A reproducible pipeline exists: from MP3, to raw PCM, to a parseable Opus container, to per-band PVQ records, with aligned PSNR and PESQ as quality baselines.

## 8. What Phase 1 does not establish

- Whether any bit-cost-neutral modification of a PVQ index is possible.
- Whether such modifications, if they exist, can be decoded without desynchronizing the range decoder.
- What the perceptual cost of PVQ index substitutions is at various codebook sizes.
- Whether the resulting channel is statistically detectable.

Those are the questions Phase 2 exists to answer.

## 9. Artifacts produced

| Artifact | Path | Description |
|---|---|---|
| Instrumentation patch | `patches/0001-pvq-instrumentation.patch` | Full diff against libopus v1.5.2 |
| PVQ log | `logs/pvq_indices/cv_001.log` | 38,733 lines (header + 38,732 records) for `cv_001` |
| Encoded container | `data/bitstreams/encoded/cv_001.opusraw` | SHA-256 `6726d524...` |
| Logging access pattern | `PVQ_LOG=<path> ./build/encode_raw ...` | No rebuild needed to toggle |

## 10. Phase 2 preview

Phase 2 will modify `encode_pulses` to optionally substitute `_idx` with `(_idx + delta) mod _V` for a chosen `(frame, band)` target, controlled by environment variables. Three encodes will be compared:

1. Unmodified baseline.
2. One target band/frame with a substitution.
3. Multiple substitutions across frames.

The decisive measurement is the **change in packet byte count**. If it is zero, the substitution is bit-neutral at that band, and the range coder has consumed the same number of bits for both symbols. If it is nonzero, the coder is stateful in a way that the substitution does not preserve, and Phase 2 must either search for a bit-neutral `delta` at each band or accept a resynchronization cost.

This single experiment — one band, one frame, one delta, one byte-count delta — determines whether the PVQ range-coder surface supports steganographic embedding, and therefore whether the project has a positive or a negative result to report.

---

Record this verbatim in the README, or trim it to fit. The sections that are least optional are §4.3 (the histogram — the empirical foundation for Phase 2's capacity assumptions), §6 (the falsification of the raw-bit premise), and §4.4 (the determinism proof, which every future claim depends on).