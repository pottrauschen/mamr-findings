#!/usr/bin/env python3
"""Gates of the NES oracle pipeline (docs/nes-architecture.md section 7,
docs/nes-oracles.md).

    gates.py selftest
        the gate logic on synthetic hash files, no oracle needed
    gates.py g2 ORACLE ROM [--frames N] [--input FILE]
        run ORACLE twice on ROM; the two outputs must be byte-identical
    gates.py g3 ORACLE ROM [--frames N] [--inject F:ADDR:XOR]
        run ORACLE clean and with one internal RAM byte flipped at frame F;
        compare.py must report exactly frame F and field ram
    gates.py dumpcheck ORACLE ROM [--frames N] [--dump-at F,F,...]
        the writer's hashing against hashline.py: every dumped frame,
        rehashed, must give the oracle's own F line fields
    gates.py cross ROM [--frames N] [--input FILE] [--require f1,f2,...] [--from F]
        MesenCE against MAME (G2, oracle against oracle): per-field count
        of differing frames; passes when the --require fields are equal in
        every frame from F on (default 1; none required by default: the
        comparison is a record)
    gates.py accuracycoin ORACLE ROM ASM [--expect P/R] [--expect-fail S,...] [--skip S,...]
        run every AccuracyCoin test with inputs/accuracycoin-all.txt, decode
        the T line with accuracycoin.py; passes when the ROM's tally is P/R
        and the failing tests are exactly the result symbols S (default:
        every test passes). --skip marks tests skipped before the run (for
        a test that hangs the oracle); a skipped test is neither passed
        nor failed. A test that hangs the oracle (no progress for
        ACC_HANG_FRAMES frames, or the pass going back to an earlier test)
        is reported and skipped in a rerun. With
        --per-page every menu page runs from power-on on its own (RIGHT to
        the page, then A), so a test that breaks the ROM's own state only
        affects its page; --expect is not used then (the ROM keeps no
        tally for a page)
    gates.py reference ORACLE ROM REFERENCE [--frames N] [--input FILE]
        the ctest entry for a checked-in file: G2 for ORACLE, then every
        field of the first N frames equal to REFERENCE (cyc and dot too for
        MesenCE); the run must have at least N F lines
    gates.py ab ROM [--frames N] [--input FILE] [--require f,f@F,...] [--reference FILE]
        MAMR against MesenCE: MesenCE with a dump of frame 1, MAMR started
        from that dump's palette RAM; the --require fields (default all:
        every field, inp, cyc, dot; "f@F" from frame F on) must be equal.
        With --reference FILE MAMR runs alone against that file
    gates.py g1 --cmd "COMMAND {out}" [--cmd2 ...] [--expect F:field=value,...]
        MAMR against MAMR: runs COMMAND twice ({out} is replaced by the
        output path) and requires byte-identical hash lines; with --cmd2 a
        second command (stage S against stage E) must give equal fields;
        with --expect the F line of frame F must hold those field values
        (a recorded picture, for example, that the primary oracle shares)

ORACLE is mesence, mame or mamr, found through the environment: MAMR
(MAMR's nes_headless, not published; else "nes_headless" in PATH), MESEN (the
MesenCE executable, else "Mesen" in PATH; started through
mesen/run_mesen.sh) and MAME (else "mame" in PATH; started through
mame/run_mame.sh). Work files go to --work DIR (default: a new temporary
directory, removed afterwards unless --keep).

The console region (docs/nes-oracles.md section 8): with NES_REGION=pal
in the environment every oracle runs a PAL console (MAMR --region pal,
MesenCE MESEN_REGION=Pal, MAME driver nespal); NES_REGION=auto lets MAMR
decide from its cartridge database while MesenCE and MAME run PAL; unset,
everything runs NTSC as before.

Exit codes: 0 gate passed, 1 gate failed, 2 oracle or input missing
(skip), 3 usage error.
"""
import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import accuracycoin  # noqa: E402
import compare  # noqa: E402
import hashline as H  # noqa: E402

SKIP = 2
ORACLES = ("mesence", "mame", "mamr")
ACC_INPUT = os.path.join(HERE, "inputs", "accuracycoin-all.txt")
ACC_FRAMES = 20000
# A test that runs this long has hung (the longest test of the pinned
# commit takes under 300 frames in MesenCE).
ACC_HANG_FRAMES = 1200
ACC_MAX_HANGS = 10


# Extra switches for MAMR's runs (gates.py --mamr-args "...").
MAMR_EXTRA = []


class Skip(Exception):
    pass


def find_oracle(name):
    if name == "mesence":
        p = os.environ.get("MESEN") or shutil.which("Mesen")
        var = "MESEN"
    elif name == "mame":
        p = os.environ.get("MAME") or shutil.which("mame")
        var = "MAME"
    elif name == "mamr":
        p = os.environ.get("MAMR") or shutil.which("nes_headless")
        var = "MAMR"
    else:
        raise ValueError("unknown oracle " + name)
    if not p or not os.access(p, os.X_OK):
        raise Skip("%s not found (set %s)" % (name, var))
    return p


def rom_id(rom):
    with open(rom, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


FH_KEYS = ("FH_OUT", "FH_FRAMES", "FH_INPUT", "FH_INJECT", "FH_DUMP_DIR", "FH_DUMP_AT", "FH_DUMP_EVERY", "FH_ACC",
           "FH_STOP_AFTER_T", "FH_ACC_SKIP", "FH_ACC_HANG", "FH_ACC_FLAG", "FH_ROM_ID", "FH_FILL")


def run_oracle(name, rom, out, frames, work, fill="00", inject=None, dump_dir=None, dump_at=None, input_script=None,
               acc=False, acc_skip=None, acc_hang=0, acc_flag=None, palette=None):
    """Runs one oracle and returns the wall time in seconds. The output
    file is removed first, so a failed run never leaves an old file."""
    if not os.path.exists(rom):
        raise Skip("ROM missing: " + rom)
    exe = find_oracle(name)
    if os.path.exists(out):
        os.unlink(out)
    env = {k: v for k, v in os.environ.items() if k not in FH_KEYS}
    env.update(FH_OUT=os.path.abspath(out), FH_FRAMES=str(frames), FH_ROM_ID=rom_id(rom))
    if inject:
        env["FH_INJECT"] = inject
    if dump_dir:
        env["FH_DUMP_DIR"] = os.path.abspath(dump_dir)
        env["FH_DUMP_AT"] = ",".join(str(f) for f in dump_at or [])
    if input_script:
        env["FH_INPUT"] = os.path.abspath(input_script)
    if acc:
        env["FH_ACC"] = "1"
        env["FH_STOP_AFTER_T"] = "1"
        if acc_skip:
            env["FH_ACC_SKIP"] = ",".join("%x" % a for a in acc_skip)
        if acc_hang:
            env["FH_ACC_HANG"] = str(acc_hang)
        if acc_flag:
            env["FH_ACC_FLAG"] = acc_flag
    region = os.environ.get("NES_REGION", "")
    t0 = time.time()
    if name == "mamr":
        cmd = [exe, os.path.abspath(rom), "--frames", str(frames), "--out", os.path.abspath(out), "--fill", fill]
        if region in ("pal", "ntsc"):
            cmd += ["--region", region]
        if inject:
            cmd += ["--inject", inject]
        if dump_dir:
            cmd += ["--dump-dir", os.path.abspath(dump_dir), "--dump-at", ",".join(str(f) for f in dump_at or [])]
        if input_script:
            cmd += ["--input", os.path.abspath(input_script)]
        if acc:
            cmd += ["--acc", "--stop-after-t"]
            if acc_skip:
                cmd += ["--acc-skip", ",".join("%x" % a for a in acc_skip)]
            if acc_hang:
                cmd += ["--acc-hang", str(acc_hang)]
            if acc_flag:
                cmd += ["--acc-flag", acc_flag]
        if palette:
            cmd += ["--palette", os.path.abspath(palette)]
        cmd += MAMR_EXTRA
    elif name == "mesence":
        env.update(MESEN=exe, MESEN_FILL=fill, MESEN_NES_HOME=os.path.join(work, "mesen-home"))
        if region in ("pal", "auto"):
            env["MESEN_REGION"] = "Pal"
        cmd = [os.path.join(HERE, "mesen", "run_mesen.sh"), os.path.abspath(rom),
               os.path.join(HERE, "mesen", "nesfh.lua")]
    else:
        env.update(MAME=exe, MAME_WORK=os.path.join(work, "mame-work"))
        if region in ("pal", "auto"):
            env["MAME_DRIVER"] = "nespal"
        cmd = [os.path.join(HERE, "mame", "run_mame.sh"), os.path.abspath(rom)]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if name == "mamr" and r.returncode == 4:
        r = subprocess.CompletedProcess(r.args, 0, r.stdout, r.stderr) # jammed CPU: no further F lines
    if r.returncode != 0:
        raise RuntimeError("%s failed (%d): %s" % (name, r.returncode, (r.stderr or r.stdout).strip()[-500:]))
    if not os.path.exists(out):
        raise RuntimeError("%s wrote no output" % name)
    if not acc:
        check_count(out, frames, name)
    return time.time() - t0


def check_count(path, frames, name):
    """The run must have written exactly frames F lines, numbered 1..frames."""
    _, recs, _ = H.read_file(path)
    nums = [r["n"] for r in recs]
    if nums != list(range(1, frames + 1)):
        raise RuntimeError("%s wrote %d of %d F lines" % (name, len(nums), frames))


def same_bytes(a, b):
    with open(a, "rb") as f:
        x = f.read()
    with open(b, "rb") as f:
        y = f.read()
    return x == y, len(x)


def gate_g2(work, oracle, rom, frames, input_script, log):
    a, b = os.path.join(work, oracle + "-1.hash"), os.path.join(work, oracle + "-2.hash")
    t1 = run_oracle(oracle, rom, a, frames, work, input_script=input_script)
    t2 = run_oracle(oracle, rom, b, frames, work, input_script=input_script)
    same, n = same_bytes(a, b)
    log("G2 %s: %s (%d bytes, %.1f s and %.1f s, %.0f frames/s)" % (
        oracle, "identical" if same else "DIFFERENT", n, t1, t2, frames / max(t1, 1e-6)))
    if not same:
        compare.compare_lines(a, b, timing=True, out=log)
    return same, a


def gate_g3(work, oracle, rom, frames, inject, log):
    f, addr, _ = inject.split(":")
    clean, faulty = os.path.join(work, oracle + "-clean.hash"), os.path.join(work, oracle + "-fault.hash")
    run_oracle(oracle, rom, clean, frames, work)
    run_oracle(oracle, rom, faulty, frames, work, inject=inject)
    logs = []
    ok, diffs = compare.compare_lines(clean, faulty, out=logs.append)
    for line in logs:
        log("  " + line)
    want = "first divergence: frame %d/%d fields ram" % (int(f), int(f))
    good = (not ok) and any(line == want for line in logs) and \
        all(v == 0 for k, v in diffs.items() if k != "ram") and diffs.get("ram", 0) >= 1
    log("G3 %s: %s (inject %s at frame %s, address $%s)" % (oracle, "ok" if good else "FAILED", inject, f, addr))
    return good


def gate_dumpcheck(work, oracle, rom, frames, dump_at, log):
    out = os.path.join(work, oracle + "-dump.hash")
    d = os.path.join(work, oracle + "-dumps")
    os.makedirs(d, exist_ok=True)
    run_oracle(oracle, rom, out, frames, work, dump_dir=d, dump_at=dump_at)
    _, recs, _ = H.read_file(out)
    ok = True
    for fr in dump_at:
        r = recs[fr - 1]
        fields = H.load_dump(d, fr)
        for name in H.FIELDS:
            if r[name] == "-":
                if name in fields:
                    ok = False
                    log("  frame %d %s: '-' in the line but dumped" % (fr, name))
                continue
            data = fields.get(name)
            if data is None:
                ok = False
                log("  frame %d %s: not dumped" % (fr, name))
                continue
            got = data.hex() if name in H.RAW_FIELDS else "%016x" % H.fnv1a64(data)
            if got != r[name]:
                ok = False
                log("  frame %d %s: line %s, dump %s" % (fr, name, r[name], got))
    log("dumpcheck %s: %s (frames %s)" % (oracle, "ok" if ok else "FAILED", ",".join(map(str, dump_at))))
    return ok


def gate_cross(work, rom, frames, input_script, require, log, start=1):
    a, b = os.path.join(work, "mesence.hash"), os.path.join(work, "mame.hash")
    run_oracle("mesence", rom, a, frames, work, input_script=input_script)
    run_oracle("mame", rom, b, frames, work, input_script=input_script)
    logs = []
    _, diffs = compare.compare_lines(a, b, out=logs.append)
    for line in logs:
        log("  " + line)
    _, ra, _ = H.read_file(a)
    _, rb, _ = H.read_file(b)
    for k in H.FIELDS:
        skipped = any(r.get(k) == "-" for r in ra + rb)
        log("  %-7s %s" % (k, "not compared ('-')" if skipped else "%d of %d frames differ" % (diffs.get(k, 0),
                                                                                              min(len(ra), len(rb)))))
    bad = []
    for k in require:
        frames_bad = [x["n"] for x, y in zip(ra, rb) if x["n"] >= start and x.get(k) != y.get(k)]
        if frames_bad:
            bad.append(k)
            log("  required %s differs from frame %d on in %d frames, first %d" % (k, start, len(frames_bad),
                                                                                  frames_bad[0]))
    log("cross: %s%s" % ("ok" if not bad else "FAILED in " + ",".join(bad),
                         " (required equal from frame %d: %s)" % (start, ",".join(require)) if require
                         else " (record only)"))
    return not bad



def gate_accuracycoin(work, oracle, rom, asm, expect, expect_fail, skip, log):
    out = os.path.join(work, oracle + "-acc.hash")
    if not os.path.exists(asm):
        raise Skip("AccuracyCoin source missing: " + asm)
    tests = accuracycoin.parse_asm(asm)
    addr = {t["symbol"]: t["address"] for t in tests}
    unknown = [s for s in skip if s not in addr]
    if unknown:
        raise RuntimeError("unknown result symbols: " + ",".join(unknown))
    skip = list(skip)
    hung = []
    t = 0.0
    while True:
        t += run_oracle(oracle, rom, out, ACC_FRAMES, work, input_script=ACC_INPUT, acc=True,
                        acc_skip=[addr[s] for s in skip], acc_hang=ACC_HANG_FRAMES)
        hang = read_hang(out)
        if hang is None:
            break
        # The test at the hang position; when it is skipped already, the
        # hang follows the test before it (a test that left the ROM's own
        # state broken), which is skipped next.
        test = accuracycoin.test_at(tests, hang[0], hang[1])
        what = "ran"
        if test is not None and test["symbol"] in skip:
            k = tests.index(test)
            test = tests[k - 1] if k > 0 else None
            what = "left the ROM hanging after it; it ran"
        if test is None or test["symbol"] in skip or len(hung) >= ACC_MAX_HANGS:
            log("accuracycoin %s: FAILED, hang at page %d index %d (frame %d) not resolvable" % (
                oracle, hang[0] + 1, hang[1], hang[2]))
            return False
        log("  hang: %s / %s (page %d, index %d) %s, %s; rerun with it skipped" % (
            test["suite"], test["name"], test["page"] + 1, test["index"], what, hang_text(hang)))
        hung.append(test["symbol"])
        skip.append(test["symbol"])
    if hung:
        log("  tests that hang %s: %s" % (oracle, ",".join(hung)))
    _, _, tallies = H.read_file(out)
    if not tallies:
        log("accuracycoin %s: FAILED, no T line within %d frames" % (oracle, ACC_FRAMES))
        return False
    accuracycoin.decode(asm, out, out=log)
    frame, passed, run, data = accuracycoin.read_t(out)
    rows = accuracycoin.results_of(tests, data)
    fails = sorted(r["symbol"] for r in rows if r["status"] not in ("pass", "skipped"))
    want_tally = expect or "%d/%d" % (run, run)
    want_fails = sorted(expect_fail)
    ok = "%d/%d" % (passed, run) == want_tally and fails == want_fails
    log("accuracycoin %s: %s (tally %d/%d at frame %d, %.0f s; expected %s%s)" % (
        oracle, "ok" if ok else "FAILED", passed, run, frame, t, want_tally,
        "" if fails == want_fails else "; failing %s, expected %s" % (",".join(fails) or "none",
                                                                      ",".join(want_fails) or "none")))
    return ok


def page_script(path, page):
    """Input script: wait for the menu, RIGHT page times, then A (the run of
    every test on the page; AccuracyCoin README "Navigating the menus")."""
    with open(path, "w") as f:
        f.write("# generated by gates.py: run every test on page %d\nWAIT 30\n" % (page + 1))
        for _ in range(page):
            f.write("HOLD RIGHT\nWAIT 3\nRELEASE RIGHT\nWAIT 3\n")
        f.write("WAIT 10\nHOLD A\nWAIT 4\nRELEASE A\n")


def gate_accuracycoin_pages(work, oracle, rom, asm, expect_fail, skip, log):
    """Every page in a run of its own, from power-on; hangs are skipped per
    page. Returns (ok, results by symbol)."""
    tests = accuracycoin.parse_asm(asm)
    addr = {t["symbol"]: t["address"] for t in tests}
    pages = sorted({t["page"] for t in tests if t["page"] >= 0})
    results = {}
    hung = []
    t_total = 0.0
    for page in pages:
        mine = [t for t in tests if t["page"] == page and 0x400 <= t["address"] <= 0x4FF]
        if not mine:
            continue
        script = os.path.join(work, "page%02d.txt" % page)
        page_script(script, page)
        out = os.path.join(work, "%s-page%02d.hash" % (oracle, page))
        page_skip = [s for s in skip if s in {t["symbol"] for t in mine}]
        while True:
            t_total += run_oracle(oracle, rom, out, ACC_FRAMES, work, input_script=script, acc=True,
                                  acc_skip=[addr[s] for s in page_skip], acc_hang=ACC_HANG_FRAMES, acc_flag="34")
            hang = read_hang(out)
            if hang is None:
                break
            test = accuracycoin.test_at(tests, hang[0], hang[1])
            if test is None or test["symbol"] in page_skip or hang[0] != page or len(hung) >= ACC_MAX_HANGS:
                log("  page %d: hang at page %d index %d not resolvable" % (page + 1, hang[0] + 1, hang[1]))
                return False, results
            log("  hang: %s / %s (page %d, index %d), %s; rerun with it skipped" % (
                test["suite"], test["name"], page + 1, test["index"], hang_text(hang)))
            hung.append(test["symbol"])
            page_skip.append(test["symbol"])
        _, _, tallies = H.read_file(out)
        if not tallies:
            log("  page %d: no T line" % (page + 1))
            return False, results
        data = bytes.fromhex(tallies[-1]["results"])
        for r in accuracycoin.results_of(mine, data):
            results[r["symbol"]] = r
    rows = [results[t["symbol"]] for t in tests if t["symbol"] in results]
    for r in rows:
        if r["status"] != "pass":
            log("  %-28s %-34s $%03X %s%s" % (r["suite"][:28], r["name"][:34], r["address"], r["status"],
                                             "" if r["code"] is None else " code %X" % r["code"]))
    npass = sum(1 for r in rows if r["status"] == "pass")
    fails = sorted(r["symbol"] for r in rows if r["status"] not in ("pass", "skipped"))
    ok = fails == sorted(expect_fail) and all(r["status"] != "not run" for r in rows)
    log("accuracycoin %s (per page): %s (%d tests: %d passed, %d failed, %d skipped%s; %.0f s)" % (
        oracle, "ok" if ok else "FAILED", len(rows), npass, len(fails),
        sum(1 for r in rows if r["status"] == "skipped"), "; hung: " + ",".join(hung) if hung else "", t_total))
    if fails != sorted(expect_fail):
        log("  failing %s, expected %s" % (",".join(fails) or "none", ",".join(sorted(expect_fail)) or "none"))
    return ok, results


def hang_text(hang):
    if hang[3] == "restart":
        return "after it the pass went back to an earlier test (frame %d)" % hang[2]
    return "no progress for %d frames (frame %d)" % (ACC_HANG_FRAMES, hang[2])


def read_hang(path):
    """(page, index, frame, reason) of a "# hang" comment, or None; reason
    is "stuck" (no progress) or "restart" (the pass went back)."""
    with open(path) as f:
        for line in f:
            if line.startswith("# hang "):
                kv = dict(x.split("=") for x in line.split()[2:])
                return int(kv["page"]), int(kv["index"]), int(kv["frame"]), kv.get("reason", "stuck")
    return None


def gate_reference(work, oracle, rom, reference, frames, input_script, log):
    if not os.path.exists(reference):
        raise Skip("reference missing: " + reference)
    same, path = gate_g2(work, oracle, rom, frames, input_script, log)
    logs = []
    ok, _ = compare.compare_lines(path, reference, timing=(oracle == "mesence"), frames=frames, out=logs.append)
    for line in logs:
        log("  " + line)
    _, ref, _ = H.read_file(reference)
    if len(ref) < frames:
        log("reference has %d F lines, expected at least %d" % (len(ref), frames))
        ok = False
    log("reference %s: %s" % (oracle, "ok" if same and ok else "FAILED"))
    return same and ok


def expect_spec(text):
    """--expect for g1: "F:field=value,..." -> [(F, field, value)]."""
    out = []
    for item in [x for x in (text or "").split(",") if x]:
        frame, _, kv = item.partition(":")
        field, _, value = kv.partition("=")
        if not frame.isdigit() or not field or not value:
            raise ValueError("bad --expect item " + item)
        out.append((int(frame), field, value))
    return out


def check_expect(path, expect, log):
    """True when every (frame, field, value) of expect holds in path."""
    _, recs, _ = H.read_file(path)
    by_n = {r["n"]: r for r in recs}
    ok = True
    for frame, field, value in expect:
        got = by_n.get(frame, {}).get(field)
        if got != value:
            ok = False
        log("  expect frame %d %s=%s: %s" % (frame, field, value, "ok" if got == value else "got %s" % got))
    return ok


def gate_g1(work, cmd, cmd2, log, expect=None):
    outs = []
    for i, c in enumerate([cmd, cmd, cmd2] if cmd2 else [cmd, cmd]):
        out = os.path.join(work, "mamr-%d.hash" % i)
        r = subprocess.run(shlex.split(c.replace("{out}", out)), capture_output=True, text=True)
        if r.returncode == 2:
            raise Skip("input missing: " + r.stderr.strip()[-300:])
        if r.returncode != 0:
            raise RuntimeError("command failed (%d): %s" % (r.returncode, r.stderr.strip()[-500:]))
        outs.append(out)
    same, n = same_bytes(outs[0], outs[1])
    log("G1: %s (%d bytes)" % ("identical" if same else "DIFFERENT", n))
    ok = same
    if cmd2:
        logs = []
        eq, _ = compare.compare_lines(outs[0], outs[2], timing=True, out=logs.append)
        for line in logs:
            log("  " + line)
        ok = ok and eq
    if expect:
        ok = check_expect(outs[0], expect, log) and ok
    return ok


def require_spec(text):
    """--require for ab: "field" or "field@F" (equal from frame F on);
    "all" is every state field with inp, cyc and dot, except snd (format
    version 2: MAMR's audio samples, which MesenCE cannot write)."""
    out = []
    for item in [x for x in (text or "all").split(",") if x]:
        name, _, start = item.partition("@")
        names = [f for f in H.FIELDS if f != "snd"] + ["inp", "cyc", "dot"] if name == "all" else [name]
        for n in names:
            out.append((n, int(start or 1)))
    return out


def gate_ab(work, rom, frames, input_script, require, reference, log):
    """MAMR against MesenCE (the A/B comparison of docs/nes-oracles.md
    section 6): MesenCE runs with a dump of frame 1, MAMR starts from that
    dump's palette RAM (the power-on palette is unspecified on the
    hardware, docs/nes-ppu-spec.md section 12), and the required fields
    must be equal. With a reference file, MAMR runs without the oracle
    (and with its own power-on palette) against that file."""
    a = os.path.join(work, "mesence.hash")
    b = os.path.join(work, "mamr.hash")
    palette = None
    if reference:
        a = reference
        if not os.path.exists(a):
            raise Skip("reference missing: " + a)
    else:
        d = os.path.join(work, "mesence-dump")
        os.makedirs(d, exist_ok=True)
        run_oracle("mesence", rom, a, frames, work, input_script=input_script, dump_dir=d, dump_at=[1])
        palette = os.path.join(d, "f000001.pal.bin")
    t = run_oracle("mamr", rom, b, frames, work, input_script=input_script, palette=palette)
    logs = []
    compare.compare_lines(a, b, timing=True, out=logs.append)
    for line in logs:
        log("  " + line)
    _, ra, _ = H.read_file(a)
    _, rb, _ = H.read_file(b)
    n = min(len(ra), len(rb))
    bad = []
    if n < frames:
        bad.append("frames")
        log("  only %d of %d frames in both files" % (n, frames))
    for k, start in require:
        frames_bad = [x["n"] for x, y in zip(ra[:n], rb[:n]) if x["n"] >= start and x.get(k) != y.get(k)]
        if frames_bad:
            bad.append(k)
            log("  required %s differs from frame %d on in %d frames, first %d" % (k, start, len(frames_bad),
                                                                                  frames_bad[0]))
    log("ab: %s (%d frames, MAMR %.1f s; required %s)" % ("ok" if not bad else "FAILED in " + ",".join(bad), n, t,
                                                          ",".join("%s@%d" % r for r in require)))
    return not bad


def selftest():
    fails = []

    def check(cond, what):
        if not cond:
            fails.append(what)

    d = tempfile.mkdtemp()
    try:
        def write(path, frames, fault=None, dash=None):
            fields = {"cpu": H.cpu_bytes(1, 2, 3, 0xFD, 0x24), "ram": bytes(2048), "vram": bytes(4096),
                      "oam": bytes(256), "pal": bytes(32), "prgram": bytes(8192), "ppu": bytes(11),
                      "prgmap": bytes(16), "chrmap": bytes(32), "mirq": bytes(4), "img": bytes(H.FIXED_SIZES["img"])}
            chain = H.FNV_BASIS
            with open(path, "w") as f:
                f.write(H.format_header("t", "0" * 40) + "\n")
                for n in range(1, frames + 1):
                    fl = dict(fields)
                    if fault and n >= fault:
                        fl["ram"] = bytes([0x5A]) + bytes(2047)
                    if dash:
                        fl[dash] = None
                    line, chain = H.format_f(n, n - 1, 100 * n, 300 * n, 0xC000, fl, chain)
                    f.write(line + "\n")

        a, b, c = (os.path.join(d, x + ".hash") for x in "abc")
        write(a, 20)
        write(b, 20)
        write(c, 20, fault=7)
        check(same_bytes(a, b)[0], "same bytes")
        check(not same_bytes(a, c)[0], "different bytes")
        logs = []
        ok, diffs = compare.compare_lines(a, c, out=logs.append)
        check(not ok and diffs["ram"] == 14 and "first divergence: frame 7/7 fields ram" in logs,
              "fault seen: %r" % logs)
        try:
            check_count(a, 20, "t")
        except RuntimeError:
            fails.append("check_count 20")
        try:
            check_count(a, 21, "t")
            fails.append("check_count 21 accepted")
        except RuntimeError:
            pass
        _, recs, _ = H.read_file(a)
        quiet = []
        check(check_expect(a, [(5, "cpu", recs[4]["cpu"])], quiet.append), "expect holds")
        check(not check_expect(a, [(5, "cpu", "00")], quiet.append), "expect fails")
        check(not check_expect(a, [(99, "cpu", recs[4]["cpu"])], quiet.append), "expect missing frame")
        check(expect_spec("600:img=ab,7:cpu=01") == [(600, "img", "ab"), (7, "cpu", "01")], "expect_spec")
        try:
            find_oracle("nonesuch")
            fails.append("unknown oracle accepted")
        except ValueError:
            pass
    finally:
        shutil.rmtree(d)
    if fails:
        print("gates selftest FAILED:", ", ".join(fails))
        return 1
    print("gates selftest ok")
    return 0


def parse(argv, flags, valued):
    opts = {f: False for f in flags}
    opts.update({v: None for v in valued})
    rest = []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a in flags:
            opts[a] = True
        elif a in valued:
            if not args:
                raise ValueError("option %s needs a value" % a)
            opts[a] = args.pop(0)
        else:
            rest.append(a)
    return opts, rest


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 3
    cmd = argv[1]
    if cmd == "selftest":
        return selftest()
    try:
        opts, rest = parse(argv[2:], ["--keep", "--per-page"], ["--frames", "--input", "--inject", "--dump-at", "--require", "--mamr-args", "--reference",
                                                 "--expect", "--expect-fail", "--skip", "--from", "--work", "--cmd", "--cmd2"])
    except ValueError as e:
        print(e)
        return 3
    frames = int(opts["--frames"] or 300)
    if opts["--mamr-args"]:
        MAMR_EXTRA.extend(shlex.split(opts["--mamr-args"]))
    work = opts["--work"] or tempfile.mkdtemp(prefix="nes-gates-")
    os.makedirs(work, exist_ok=True)
    log = print
    try:
        if cmd in ("g2", "g3", "dumpcheck", "accuracycoin", "reference"):
            if not rest or rest[0] not in ORACLES:
                print("first argument must be one of " + ", ".join(ORACLES))
                return 3
        if cmd == "g2" and len(rest) == 2:
            ok = gate_g2(work, rest[0], rest[1], frames, opts["--input"], log)[0]
        elif cmd == "g3" and len(rest) == 2:
            ok = gate_g3(work, rest[0], rest[1], frames, opts["--inject"] or "%d:0100:5a" % (frames // 2), log)
        elif cmd == "dumpcheck" and len(rest) == 2:
            at = [int(x) for x in (opts["--dump-at"] or "1,%d,%d" % (frames // 2, frames)).split(",")]
            ok = gate_dumpcheck(work, rest[0], rest[1], frames, at, log)
        elif cmd == "cross" and len(rest) == 1:
            req = [x for x in (opts["--require"] or "").split(",") if x]
            ok = gate_cross(work, rest[0], frames, opts["--input"], req, log, int(opts["--from"] or 1))
        elif cmd == "accuracycoin" and len(rest) == 3:
            ef = [x for x in (opts["--expect-fail"] or "").split(",") if x]
            sk = [x for x in (opts["--skip"] or "").split(",") if x]
            if opts["--per-page"]:
                if not os.path.exists(rest[2]):
                    raise Skip("AccuracyCoin source missing: " + rest[2])
                ok = gate_accuracycoin_pages(work, rest[0], rest[1], rest[2], ef, sk, log)[0]
            else:
                ok = gate_accuracycoin(work, rest[0], rest[1], rest[2], opts["--expect"], ef, sk, log)
        elif cmd == "reference" and len(rest) == 3:
            ok = gate_reference(work, rest[0], rest[1], rest[2], frames, opts["--input"], log)
        elif cmd == "ab" and len(rest) == 1:
            ok = gate_ab(work, rest[0], frames, opts["--input"], require_spec(opts["--require"]), opts["--reference"],
                         log)
        elif cmd == "g1" and opts["--cmd"]:
            ok = gate_g1(work, opts["--cmd"], opts["--cmd2"], log, expect_spec(opts["--expect"]))
        else:
            print(__doc__)
            return 3
        return 0 if ok else 1
    except Skip as e:
        print("SKIP: %s" % e)
        return SKIP
    except RuntimeError as e:
        print("FAILED: %s" % e)
        return 1
    except ValueError as e:
        print(e)
        return 3
    finally:
        if not opts["--keep"] and not opts["--work"]:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
