#!/usr/bin/env python3
"""Run the catalogued test ROMs of christopherpow/nes-test-roms through the
oracles and decode their verdicts (docs/nes-test-evidence.md section 3).

The collection has no licence: it is used locally only, as an external
judge; nothing of it (no ROM, no output) enters the repository. This file
holds only the catalogue (file names, what they test, how they report).

    testroms.py selftest
    testroms.py run DIR [--oracles mesence,mame,mamr] [--only SUBSTR] [--out TSV] [--work DIR]
        DIR is a checkout of nes-test-roms. Runs every catalogued ROM in
        each oracle, one after the other, and prints one row per ROM and
        oracle; --out writes the rows as tab-separated values
    testroms.py table TSV
        the rows of a TSV as the Markdown table of the evidence register

A verdict comes from blargg's result protocol at $6000 when the ROM uses
it (format section 9: status 0 passed, else the failure code, with the
ROM's text), otherwise from the text on the nametables at the end of the run:
"PASSED" passed, "FAILED" or "FAIL" failed, "All tests complete"
passed unless a failing instruction is listed (the 2005 CPU suite), a lone result code "$01"
passed and any other code failed (the 2005 suites: "A result code of 1
always indicates that all tests were passed"). Everything else is
"unclear" with the screen text, to be judged by eye.

Exit codes: 0 success, 1 failure, 2 input or oracle missing, 3 usage error.
"""
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gates  # noqa: E402
import hashline as H  # noqa: E402

# (path in the collection, area, phase, frames). frames is the cap of the
# run; a ROM with the $6000 protocol ends at its result.
CATALOG = [
    ("instr_test-v5/official_only.nes", "CPU instructions (official)", "N1", 4000),
    ("instr_test-v5/all_instrs.nes", "CPU instructions (all, unofficial included)", "N1", 6000),
    ("instr_misc/instr_misc.nes", "CPU instruction details (wrap, dummy reads)", "N1", 3000),
    ("instr_timing/instr_timing.nes", "CPU instruction timing (APU timer based)", "N1/N2", 4000),
    ("cpu_timing_test6/cpu_timing_test.nes", "CPU instruction timing (PPU based)", "N1/N2", 1500),
    ("branch_timing_tests/1.Branch_Basics.nes", "branch timing", "N1/N2", 900),
    ("branch_timing_tests/2.Backward_Branch.nes", "branch timing", "N1/N2", 900),
    ("branch_timing_tests/3.Forward_Branch.nes", "branch timing", "N1/N2", 900),
    ("cpu_dummy_reads/cpu_dummy_reads.nes", "CPU dummy reads (via $2002)", "N1/N2", 1800),
    ("cpu_dummy_writes/cpu_dummy_writes_oam.nes", "CPU dummy writes (OAM)", "N1/N2", 3000),
    ("cpu_dummy_writes/cpu_dummy_writes_ppumem.nes", "CPU dummy writes (PPU memory)", "N1/N2", 3000),
    ("cpu_exec_space/test_cpu_exec_space_ppuio.nes", "executing from I/O space (PPU)", "N1/N2", 1800),
    ("cpu_exec_space/test_cpu_exec_space_apu.nes", "executing from I/O space (APU)", "N1/N2", 1800),
    ("cpu_interrupts_v2/cpu_interrupts.nes", "CPU interrupts (CLI latency, NMI/BRK, IRQ/DMA)", "N1/N2", 4000),
    ("cpu_reset/registers.nes", "CPU registers after reset", "N1", 1800),
    ("cpu_reset/ram_after_reset.nes", "RAM after reset", "N1", 1800),
    ("blargg_nes_cpu_test5/official.nes", "CPU instructions (2005 suite, official)", "N1", 12000),
    ("blargg_nes_cpu_test5/cpu.nes", "CPU instructions (2005 suite, all)", "N1", 12000),
    ("ppu_vbl_nmi/ppu_vbl_nmi.nes", "VBlank flag and NMI timing", "N2", 4000),
    ("vbl_nmi_timing/1.frame_basics.nes", "frame length (2005)", "N2", 900),
    ("vbl_nmi_timing/2.vbl_timing.nes", "VBlank timing (2005)", "N2", 900),
    ("vbl_nmi_timing/3.even_odd_frames.nes", "odd frame skip (2005)", "N2", 900),
    ("vbl_nmi_timing/4.vbl_clear_timing.nes", "VBlank clear (2005)", "N2", 900),
    ("vbl_nmi_timing/5.nmi_suppression.nes", "NMI suppression (2005)", "N2", 900),
    ("vbl_nmi_timing/6.nmi_disable.nes", "NMI disable (2005)", "N2", 900),
    ("vbl_nmi_timing/7.nmi_timing.nes", "NMI timing (2005)", "N2", 900),
    ("ppu_open_bus/ppu_open_bus.nes", "PPU I/O latch and decay", "N2", 3000),
    ("ppu_read_buffer/test_ppu_read_buffer.nes", "$2007 read buffer", "N2", 3000),
    ("oam_read/oam_read.nes", "OAM reads via $2004", "N2", 1800),
    ("oam_stress/oam_stress.nes", "OAM writes and reads under stress", "N2", 4000),
    ("blargg_ppu_tests_2005.09.15b/palette_ram.nes", "palette RAM (2005)", "N2", 600),
    ("blargg_ppu_tests_2005.09.15b/sprite_ram.nes", "sprite RAM (2005)", "N2", 600),
    ("blargg_ppu_tests_2005.09.15b/vram_access.nes", "VRAM access (2005)", "N2", 600),
    ("blargg_ppu_tests_2005.09.15b/vbl_clear_time.nes", "VBlank clear time (2005)", "N2", 600),
    ("blargg_ppu_tests_2005.09.15b/power_up_palette.nes", "palette at power-up (2005)", "N2", 600),
    ("sprite_hit_tests_2005.10.05/01.basics.nes", "sprite 0 hit", "N2", 900),
    ("sprite_hit_tests_2005.10.05/02.alignment.nes", "sprite 0 hit", "N2", 900),
    ("sprite_hit_tests_2005.10.05/03.corners.nes", "sprite 0 hit", "N2", 900),
    ("sprite_hit_tests_2005.10.05/04.flip.nes", "sprite 0 hit", "N2", 900),
    ("sprite_hit_tests_2005.10.05/05.left_clip.nes", "sprite 0 hit", "N2", 900),
    ("sprite_hit_tests_2005.10.05/06.right_edge.nes", "sprite 0 hit", "N2", 900),
    ("sprite_hit_tests_2005.10.05/07.screen_bottom.nes", "sprite 0 hit", "N2", 900),
    ("sprite_hit_tests_2005.10.05/08.double_height.nes", "sprite 0 hit", "N2", 900),
    ("sprite_hit_tests_2005.10.05/09.timing_basics.nes", "sprite 0 hit timing", "N2", 900),
    ("sprite_hit_tests_2005.10.05/10.timing_order.nes", "sprite 0 hit timing", "N2", 900),
    ("sprite_hit_tests_2005.10.05/11.edge_timing.nes", "sprite 0 hit timing", "N2", 900),
    ("sprite_overflow_tests/1.Basics.nes", "sprite overflow", "N2", 900),
    ("sprite_overflow_tests/2.Details.nes", "sprite overflow", "N2", 900),
    ("sprite_overflow_tests/3.Timing.nes", "sprite overflow timing", "N2", 900),
    ("sprite_overflow_tests/4.Obscure.nes", "sprite overflow (evaluation bug)", "N2", 900),
    ("sprite_overflow_tests/5.Emulator.nes", "sprite overflow (emulator pitfalls)", "N2", 900),
    ("apu_test/apu_test.nes", "APU length counters, frame IRQ, DMC basics", "N2", 4000),
    ("apu_reset/4015_cleared.nes", "APU after reset", "N2", 1800),
    ("apu_reset/4017_timing.nes", "APU after reset", "N2", 1800),
    ("apu_reset/4017_written.nes", "APU after reset", "N2", 1800),
    ("apu_reset/irq_flag_cleared.nes", "APU after reset", "N2", 1800),
    ("apu_reset/len_ctrs_enabled.nes", "APU after reset", "N2", 1800),
    ("apu_reset/works_immediately.nes", "APU after reset", "N2", 1800),
    ("blargg_apu_2005.07.30/01.len_ctr.nes", "APU (2005)", "N2", 900),
    ("blargg_apu_2005.07.30/02.len_table.nes", "APU (2005)", "N2", 900),
    ("blargg_apu_2005.07.30/03.irq_flag.nes", "APU (2005)", "N2", 900),
    ("blargg_apu_2005.07.30/04.clock_jitter.nes", "APU (2005)", "N2", 900),
    ("blargg_apu_2005.07.30/05.len_timing_mode0.nes", "APU (2005)", "N2", 900),
    ("blargg_apu_2005.07.30/06.len_timing_mode1.nes", "APU (2005)", "N2", 900),
    ("blargg_apu_2005.07.30/07.irq_flag_timing.nes", "APU (2005)", "N2", 900),
    ("blargg_apu_2005.07.30/08.irq_timing.nes", "APU (2005)", "N2", 900),
    ("blargg_apu_2005.07.30/09.reset_timing.nes", "APU (2005)", "N2", 900),
    ("blargg_apu_2005.07.30/10.len_halt_timing.nes", "APU (2005)", "N2", 900),
    ("blargg_apu_2005.07.30/11.len_reload_timing.nes", "APU (2005)", "N2", 900),
    ("dmc_dma_during_read4/dma_2007_read.nes", "DMC DMA during $2007 read", "N2", 900),
    ("dmc_dma_during_read4/dma_2007_write.nes", "DMC DMA during $2007 write", "N2", 900),
    ("dmc_dma_during_read4/dma_4016_read.nes", "DMC DMA during $4016 read", "N2", 900),
    ("dmc_dma_during_read4/double_2007_read.nes", "double $2007 read", "N2", 900),
    ("dmc_dma_during_read4/read_write_2007.nes", "$2007 read-modify-write", "N2", 900),
    ("sprdma_and_dmc_dma/sprdma_and_dmc_dma.nes", "OAM DMA meeting DMC DMA", "N2", 1800),
    ("sprdma_and_dmc_dma/sprdma_and_dmc_dma_512.nes", "OAM DMA meeting DMC DMA (512 cycles)", "N2", 1800),
    ("read_joy3/count_errors.nes", "controller reads under DMC DMA", "N2", 1800),
    ("read_joy3/thorough_test.nes", "controller reads", "N2", 1800),
    ("mmc3_test_2/rom_singles/1-clocking.nes", "MMC3 counter clocking", "N2", 1800),
    ("mmc3_test_2/rom_singles/2-details.nes", "MMC3 counter details", "N2", 1800),
    ("mmc3_test_2/rom_singles/3-A12_clocking.nes", "MMC3 A12 clocking", "N2", 1800),
    ("mmc3_test_2/rom_singles/4-scanline_timing.nes", "MMC3 scanline timing", "N2", 1800),
    ("mmc3_test_2/rom_singles/5-MMC3.nes", "MMC3 revision B (new)", "N2", 1800),
    ("mmc3_test_2/rom_singles/6-MMC3_alt.nes", "MMC3 revision A (alternate)", "N2", 1800),
    ("mmc3_irq_tests/1.Clocking.nes", "MMC3 counter clocking (2006)", "N2", 900),
    ("mmc3_irq_tests/2.Details.nes", "MMC3 counter details (2006)", "N2", 900),
    ("mmc3_irq_tests/3.A12_clocking.nes", "MMC3 A12 clocking (2006)", "N2", 900),
    ("mmc3_irq_tests/4.Scanline_timing.nes", "MMC3 scanline timing (2006)", "N2", 900),
    ("mmc3_irq_tests/5.MMC3_rev_A.nes", "MMC3 revision A (Crystalis board)", "N2", 900),
    ("mmc3_irq_tests/6.MMC3_rev_B.nes", "MMC3 revision B (SMB3 board)", "N2", 900),
    # Phase N4 (docs/nes-audio-spec.md): the singles of apu_test, and the
    # tests whose verdict is heard (AUDIBLE below).
    ("apu_test/rom_singles/1-len_ctr.nes", "APU length counters", "N4", 600),
    ("apu_test/rom_singles/2-len_table.nes", "APU length table", "N4", 600),
    ("apu_test/rom_singles/3-irq_flag.nes", "APU frame IRQ flag", "N4", 600),
    ("apu_test/rom_singles/4-jitter.nes", "APU clock jitter", "N4", 600),
    ("apu_test/rom_singles/5-len_timing.nes", "APU length clock timing", "N4", 600),
    ("apu_test/rom_singles/6-irq_flag_timing.nes", "APU frame IRQ timing", "N4", 600),
    ("apu_test/rom_singles/7-dmc_basics.nes", "DMC basics", "N4", 600),
    ("apu_test/rom_singles/8-dmc_rates.nes", "DMC rates", "N4", 600),
    ("dmc_tests/buffer_retained.nes", "DMC sample buffer (heard)", "N4", 120),
    ("dmc_tests/latency.nes", "DMC start latency (heard)", "N4", 120),
    ("dmc_tests/status.nes", "DMC status bit (heard)", "N4", 120),
    ("dmc_tests/status_irq.nes", "DMC IRQ (heard)", "N4", 120),
    ("apu_mixer/dmc.nes", "mixer: DMC DAC nonlinearity (heard)", "N4", 1300),
    ("apu_mixer/noise.nes", "mixer: noise against DMC (heard)", "N4", 1300),
    ("apu_mixer/square.nes", "mixer: pulses against DMC (heard)", "N4", 1300),
    ("apu_mixer/triangle.nes", "mixer: triangle against DMC (heard)", "N4", 1300),
    # Phase P (docs/nes-hardware-spec.md section 7): the PAL ROMs, run on
    # a PAL console in every oracle (their headers say NTSC; PAL below).
    ("pal_apu_tests/01.len_ctr.nes", "PAL APU length counters", "P", 900),
    ("pal_apu_tests/02.len_table.nes", "PAL APU length table", "P", 900),
    ("pal_apu_tests/03.irq_flag.nes", "PAL APU frame IRQ flag", "P", 900),
    ("pal_apu_tests/04.clock_jitter.nes", "PAL APU clock jitter", "P", 900),
    ("pal_apu_tests/05.len_timing_mode0.nes", "PAL APU length timing, 4-step", "P", 900),
    ("pal_apu_tests/06.len_timing_mode1.nes", "PAL APU length timing, 5-step", "P", 900),
    ("pal_apu_tests/07.irq_flag_timing.nes", "PAL APU frame IRQ flag timing", "P", 900),
    ("pal_apu_tests/08.irq_timing.nes", "PAL APU frame IRQ timing", "P", 900),
    ("pal_apu_tests/10.len_halt_timing.nes", "PAL APU length halt timing", "P", 900),
    ("pal_apu_tests/11.len_reload_timing.nes", "PAL APU length reload timing", "P", 900),
    ("nmi_sync/demo_pal.nes", "PAL NMI synchronisation (seen)", "P", 120),
]

# The ROMs of a PAL console.
PAL = {c[0] for c in CATALOG if c[2] == "P"}
# Tests whose verdict is in the picture (judged by eye or against the
# readme's description): nmi_sync draws a line by timed writes.
VISUAL = {"nmi_sync/demo_pal.nes"}

# Tests whose verdict is in the sound: apu_mixer cancels a channel with
# the DMC DAC ("near silence between the beeps"; its $6000 status 0 only
# says the run ended), dmc_tests (no readme, no text) end with a fixed
# tone after their clicks. Their verdict is "audible"; the evidence
# register judges them by ear or by measurement (docs/nes-test-evidence.md
# section 4.6).
AUDIBLE = {"apu_mixer/dmc.nes", "apu_mixer/noise.nes", "apu_mixer/square.nes", "apu_mixer/triangle.nes",
           "dmc_tests/buffer_retained.nes", "dmc_tests/latency.nes", "dmc_tests/status.nes",
           "dmc_tests/status_irq.nes"}

CODE_RE = re.compile(r"^\$([0-9A-Fa-f]{2})$")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
OPCODE_LINE_RE = re.compile(r"^[0-9A-F]{2} [A-Z]{3}\b")

# Tests that print a CRC instead of a verdict, with the CRCs TASVideos
# accepts (EmulatorResources/NESAccuracyTests/TestCriteria, retrieved
# 2026-10-24): the alternatives come from the DMA phase.
ACCEPTED_CRCS = {
    "dmc_dma_during_read4/dma_2007_read.nes": {"159A7A8F", "5E3DF9C4"},
    "dmc_dma_during_read4/double_2007_read.nes": {"85CFD627", "F018C287", "440EF923", "E52F41A5"},
}


def screen_text(nt_hex):
    """The nametables ($2000-$2FFF as the N line holds them; older files
    hold nametable 0 only) as lines of ASCII (tiles $20-$7E as characters),
    rows of the attribute tables skipped."""
    data = bytes.fromhex(nt_hex)
    lines = []
    for y in range(len(data) // 32):
        if y % 32 >= 30:
            continue
        row = "".join(chr(c) if 32 <= c < 127 else " " for c in data[y * 32:(y + 1) * 32]).strip()
        if row:
            lines.append(" ".join(row.split()))
    return lines


def verdict(rs, ns, path=None):
    """(verdict, detail) from the R and N lines of one run."""
    if path in VISUAL:
        return "visual", ""
    if path in AUDIBLE:
        if rs:
            r = rs[-1]
            text = "" if r["text"] == "-" else ANSI_RE.sub("", bytes.fromhex(r["text"]).decode("ascii", "replace"))
            return "audible", ("status %s: " % r["status"] + " ".join(text.split()))[:120]
        return "audible", ""
    if rs:
        r = rs[-1]
        text = "" if r["text"] == "-" else ANSI_RE.sub("", bytes.fromhex(r["text"]).decode("ascii", "replace"))
        text = " ".join(t for t in text.replace("\n", " ").split() if t)
        st = int(r["status"], 16)
        return ("pass" if st == 0 else "fail %d" % st), text[:120]
    if not ns:
        return "no result", ""
    lines = screen_text(ns[-1]["nt"])
    joined = " | ".join(lines)
    upper = joined.upper()
    if not lines:
        return "no text", ""
    crcs = ACCEPTED_CRCS.get(path)
    if crcs is not None:
        shown = lines[-1].strip().upper()
        return ("pass" if shown in crcs else "fail"), joined[:120]
    if "PASSED" in upper:
        return "pass", joined[:120]
    if "FAILED" in upper or re.search(r"\bFAIL\b", upper):
        return "fail", joined[:120]
    if "ALL TESTS COMPLETE" in upper:
        # blargg's 2005 CPU suite lists failing instructions as "op NAME".
        bad = [t for t in lines if OPCODE_LINE_RE.match(t)]
        return ("fail" if bad else "pass"), (" | ".join(bad) if bad else "All tests complete")[:120]
    codes = [CODE_RE.match(t) for t in lines]
    # The 4 KiB of $2000-$2FFF hold each nametable twice with mirroring.
    codes = sorted(set(int(m.group(1), 16) for m in codes if m))
    if len(codes) == 1:
        return ("pass" if codes[0] == 1 else "fail %d" % codes[0]), joined[:120]
    return "unclear", joined[:120]


def run_one(oracle, rom, frames, work, path=None):
    out = os.path.join(work, oracle + ".hash")
    if os.path.exists(out):
        os.unlink(out)
    exe = gates.find_oracle(oracle)
    env = {k: v for k, v in os.environ.items() if not k.startswith("FH_")}
    env.update(FH_OUT=out, FH_FRAMES=str(frames), FH_BLARGG="1", FH_SCREEN="1", FH_STOP_AFTER_T="1")
    import subprocess
    if oracle == "mamr":
        # MAMR's own writer takes options instead of the environment; the
        # ROMs written for an MMC3 revision A board run with that revision
        # (the board parameter of docs/nes-hardware-spec.md section 3.3).
        cmd = [exe, rom, "--frames", str(frames), "--out", out, "--blargg", "--screen", "--stop-after-t"]
        if path and ("rev_A" in path or "MMC3_alt" in path):
            cmd += ["--mmc3-rev", "a"]
        if path in PAL:
            cmd += ["--region", "pal"]
        cmd += gates.MAMR_EXTRA
    elif oracle == "mesence":
        env.update(MESEN=exe, MESEN_NES_HOME=os.path.join(work, "mesen-home"))
        if path in PAL:
            env["MESEN_REGION"] = "Pal"
        cmd = [os.path.join(HERE, "mesen", "run_mesen.sh"), rom, os.path.join(HERE, "mesen", "nesfh.lua")]
    else:
        env.update(MAME=exe, MAME_WORK=os.path.join(work, "mame-work"))
        if path in PAL:
            env["MAME_DRIVER"] = "nespal"
        cmd = [os.path.join(HERE, "mame", "run_mame.sh"), rom]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if not os.path.exists(out):
        return "error", "no output (exit %d)" % r.returncode
    try:
        rs, ns = H.read_extra(out)
    except ValueError as e:
        return "error", str(e)
    return verdict(rs, ns, path)


def selftest():
    fails = []
    nt = bytearray(b" " * 960)
    nt[32 * 4 + 5:32 * 4 + 11] = b"PASSED"
    if verdict([], [{"nt": nt.hex()}])[0] != "pass":
        fails.append("screen pass")
    nt = bytearray(b" " * 960)
    nt[32 * 3 + 2:32 * 3 + 5] = b"$01"
    if verdict([], [{"nt": nt.hex()}])[0] != "pass":
        fails.append("code 1")
    nt[32 * 3 + 2:32 * 3 + 5] = b"$03"
    if verdict([], [{"nt": nt.hex()}])[0] != "fail 3":
        fails.append("code 3")
    if verdict([{"status": "00", "text": b"ok".hex()}], [])[0] != "pass":
        fails.append("blargg pass")
    if verdict([{"status": "02", "text": "-"}], [])[0] != "fail 2":
        fails.append("blargg fail")
    nt = bytearray(b" " * 960)
    nt[32 * 5 + 2:32 * 5 + 10] = b"159A7A8F"
    if verdict([], [{"nt": nt.hex()}], "dmc_dma_during_read4/dma_2007_read.nes")[0] != "pass":
        fails.append("accepted crc")
    nt[32 * 5 + 2:32 * 5 + 10] = b"DEADBEEF"
    if verdict([], [{"nt": nt.hex()}], "dmc_dma_during_read4/dma_2007_read.nes")[0] != "fail":
        fails.append("other crc")
    if verdict([{"status": "00", "text": b"\x1b[0;37mok".hex()}], [])[1] != "ok":
        fails.append("ansi")
    nt = bytearray(b" " * 960)
    nt[32 * 2:32 * 2 + 18] = b"All tests complete"
    if verdict([], [{"nt": nt.hex()}])[0] != "pass":
        fails.append("all complete")
    nt[32 * 1:32 * 1 + 6] = b"A3 LAX"
    if verdict([], [{"nt": nt.hex()}])[0] != "fail":
        fails.append("all complete with failure")
    if verdict([{"status": "00", "text": b"x".hex()}], [], "apu_mixer/dmc.nes")[0] != "audible":
        fails.append("audible")
    if verdict([], []) != ("no result", ""):
        fails.append("no result")
    if len({c[0] for c in CATALOG}) != len(CATALOG):
        fails.append("duplicate catalogue entries")
    if fails:
        print("testroms selftest FAILED:", ", ".join(fails))
        return 1
    print("testroms selftest ok")
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 3
    if argv[1] == "selftest":
        return selftest()
    if argv[1] == "table" and len(argv) == 3:
        rows = [line.rstrip("\n").split("\t") for line in open(argv[2]) if line.strip()]
        by = {}
        for path, oracle, v, detail in rows:
            by.setdefault(path, {})[oracle] = (v, detail)
        print("| ROM | MesenCE 2.2.1 | MAME 0.285 |")
        print("|---|---|---|")
        for path, d in by.items():
            print("| %s | %s | %s |" % (path, d.get("mesence", ("-",))[0], d.get("mame", ("-",))[0]))
        return 0
    if argv[1] != "run" or len(argv) < 3:
        print(__doc__)
        return 3
    try:
        opts, rest = gates.parse(argv[3:], [], ["--oracles", "--only", "--out", "--work"])
    except ValueError as e:
        print(e)
        return 3
    base = argv[2]
    if not os.path.isdir(base):
        print("SKIP: nes-test-roms missing: " + base)
        return 2
    oracles = (opts["--oracles"] or "mesence,mame").split(",")
    work = opts["--work"] or tempfile.mkdtemp(prefix="nes-testroms-")
    os.makedirs(work, exist_ok=True)
    rows = []
    try:
        for path, area, phase, frames in CATALOG:
            if opts["--only"] and opts["--only"] not in path:
                continue
            rom = os.path.join(base, path)
            if not os.path.exists(rom):
                rows.append((path, "-", "missing", ""))
                print("%-52s missing" % path)
                continue
            for oracle in oracles:
                try:
                    v, detail = run_one(oracle, os.path.abspath(rom), frames, work, path)
                except gates.Skip as e:
                    v, detail = "skip", str(e)
                rows.append((path, oracle, v, detail))
                print("%-52s %-8s %-10s %s" % (path, oracle, v, detail[:70]), flush=True)
    finally:
        if not opts["--work"]:
            shutil.rmtree(work, ignore_errors=True)
    if opts["--out"]:
        with open(opts["--out"], "w") as f:
            for r in rows:
                f.write("\t".join(x.replace("\t", " ") for x in r) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
