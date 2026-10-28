#!/usr/bin/env python3
"""Arcade oracle gates for Ikari Warriors and R-Type (docs/arcade-oracles.md
section 7).

    gates.py determinism SET FRAMES [--replay FILE] [--work DIR]
        two MAME runs of FRAMES frames each must be byte-identical
    gates.py lockstep SET FRAMES --headless EXE [--replay FILE] [--img]
            [--stage-m MODE] [--fields LIST] [--skip-field F:LIST]
            [--work DIR]
        one MAME run and one headless run (ikari_headless or
        rtype_headless, stage M) of the same frames and replay; compare.py
        lines over every field (the picture only with --img: MAME then
        draws every frame). --skip-field excludes frames of one field from
        the verdict (a documented MAME finding, docs/arcade-oracles.md
        section 6). MODE selects the judge stage M predicts: stock
        (default) is MAME 0.285 as installed; against mameref (the MAME
        variable set to the mameref build, docs/arcade-oracles.md section
        2) Ikari runs cycle (one CPU A cycle as quantum, patch 0001) and
        R-Type mameref (no second charge of a continued REP, patch 0003).
    gates.py z80steps SST_DIR
        the Z80 step table: z80steps.py selftest, the table emitted from
        MAME's z80.lst against runtime/z80_steps_table.inc, and the steps
        against the SingleStepTests z80 cycle traces in SST_DIR. z80.lst
        comes from a MAME 0.285 source tree (MAME_SRC).
    gates.py selftest

The MAME runs go through run_mame.sh (MAME, MAME_WORK, ARCADE_ROMS as
there; MAME_WORK is set per run). Exit codes: 0 pass, 1 fail, 2 skipped
(MAME, ROM set, replay, headless runner or data missing), 3 usage error.
"""
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True  # no __pycache__ in the source tree
import afh as A  # noqa: E402
import compare as C  # noqa: E402

SETS = ("ikari", "rtype")
# stage M modes per set: the first predicts MAME 0.285, the second mameref
STAGE_M_MODES = {"ikari": ("stock", "cycle"), "rtype": ("stock", "mameref")}


def roms_dir(setname):
    return os.environ.get("ARCADE_ROMS") or os.path.join(REPO, "roms", setname)


def run_mame(setname, out, frames, replay=None, img=False):
    env = dict(os.environ)
    for v in ("FH_IMG", "FH_REPLAY", "FH_ACCLOG", "FH_DUMP_DIR", "FH_DUMP_AT", "FH_DUMP_EVERY"):
        env.pop(v, None)
    if replay:
        env["FH_REPLAY"] = os.path.abspath(replay)
    if img:
        env["FH_IMG"] = "1"
    # a private MAME directory per run: two gates may run at the same time
    env["MAME_WORK"] = out + ".mamework"
    t0 = time.time()
    r = subprocess.run(["sh", os.path.join(HERE, "run_mame.sh"), setname, out, str(frames)], env=env)
    print("MAME run: %s, %d frames, exit %d, %.1f s" % (setname, frames, r.returncode, time.time() - t0))
    return r.returncode


def determinism(setname, frames, replay, work):
    a, b = os.path.join(work, "a.hash"), os.path.join(work, "b.hash")
    for p in (a, b):
        rc = run_mame(setname, p, frames, replay)
        if rc != 0:
            return 2 if rc == 2 else 1
    if not A.verify(a, frames):
        return 1
    same = filecmp.cmp(a, b, shallow=False)
    print("determinism: %s" % ("byte-identical" if same else "DIFFERENT"))
    if not same:
        C.compare_lines(a, b)
    return 0 if same else 1


def takes_roms(exe):
    """True when the runner's usage text names --roms (rtype_headless; a
    runner with the ROMs compiled in has no such option)."""
    try:
        r = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "--roms" in r.stdout + r.stderr


def headless_cmd(setname, exe, frames, out, replay, img, mode, roms=True):
    cmd = [exe]
    if roms:
        cmd += ["--roms", roms_dir(setname)]
    if setname == "rtype":
        cmd += ["--stage-m"] + (["mameref"] if mode == "mameref" else [])
    else:
        cmd += ["--stage-m", mode]
    cmd += ["--frames", str(frames), "--hash", out]
    if not img:
        cmd += ["--no-img"]
    if replay:
        cmd += ["--replay", os.path.abspath(replay)]
    return cmd


def lockstep(setname, frames, exe, replay, work, img, mode, fields, skip_fields):
    if not exe or not os.path.exists(exe):
        print("lockstep: headless runner missing: %s" % exe)
        return 2
    m, h = os.path.join(work, "mame.hash"), os.path.join(work, "mamr.hash")
    rc = run_mame(setname, m, frames, replay, img)
    if rc != 0:
        return 2 if rc == 2 else 1
    t0 = time.time()
    cmd = headless_cmd(setname, exe, frames, h, replay, img, mode, takes_roms(exe))
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL)
    print("%s: exit %d, %.1f s" % (os.path.basename(exe), r.returncode, time.time() - t0))
    if r.returncode != 0:
        return 2 if r.returncode == 2 else 1
    eq, _ = C.compare_lines(m, h, fields, True, frames, skip_fields=skip_fields)
    return 0 if eq else 1


def z80steps(sstdir, work):
    src = os.environ.get("MAME_SRC")
    lst = os.path.join(src, "src", "devices", "cpu", "z80", "z80.lst") if src else None
    if not lst or not os.path.exists(lst):
        print("z80steps: no z80.lst (set MAME_SRC to a MAME 0.285 source tree)")
        return 2
    if not os.path.isdir(sstdir):
        print("z80steps: no SingleStepTests z80 data in %s" % sstdir)
        return 2
    tool = [sys.executable, "-I", os.path.join(HERE, "z80steps.py")]
    if subprocess.run(tool + ["selftest", lst]).returncode != 0:
        return 1
    table = os.path.join(work, "z80_steps_table.inc")
    if subprocess.run(tool + ["emit", lst, table]).returncode != 0:
        return 1
    same = filecmp.cmp(table, os.path.join(REPO, "runtime", "z80_steps_table.inc"), shallow=False)
    print("z80steps: emitted table %s runtime/z80_steps_table.inc" % ("equals" if same else "DIFFERS FROM"))
    if not same:
        return 1
    return 0 if subprocess.run(tool + ["check", lst, sstdir]).returncode == 0 else 1


def parse(argv):
    """(command, positional, options); options with a value as strings,
    --skip-field as a dict field -> set of frames"""
    flags = ("--img",)
    opts, pos, skip_fields = {}, [], {}
    it = iter(argv)
    for a in it:
        if a in flags:
            opts[a] = True
        elif a == "--skip-field":
            fld, _, fr = next(it).partition(":")
            skip_fields.setdefault(fld, set()).update(C.parse_frames(fr))
        elif a.startswith("--"):
            opts[a] = next(it)
        else:
            pos.append(a)
    opts["--skip-field"] = skip_fields
    return pos, opts


def selftest():
    pos, opts = parse(["rtype", "3000", "--headless", "x", "--skip-field", "img:117-119,5", "--img"])
    ok = pos == ["rtype", "3000"] and opts["--headless"] == "x" and opts["--img"] is True
    ok = ok and opts["--skip-field"] == {"img": {5, 117, 118, 119}}
    cmd = headless_cmd("ikari", "exe", 10, "o", None, False, "stock", roms=False)
    ok = ok and cmd == ["exe", "--stage-m", "stock", "--frames", "10", "--hash", "o", "--no-img"]
    cmd = headless_cmd("rtype", "exe", 10, "o", "r", True, "stock")
    ok = ok and cmd[1:4] == ["--roms", roms_dir("rtype"), "--stage-m"] and cmd[-2:] == ["--replay", os.path.abspath("r")]
    cmd = headless_cmd("rtype", "exe", 10, "o", None, True, "mameref")
    ok = ok and cmd[3:6] == ["--stage-m", "mameref", "--frames"]
    print("gates selftest: %s" % ("ok" if ok else "FAILED"))
    return ok


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 3
    cmd = argv[1]
    if cmd == "selftest":
        return 0 if selftest() else 1
    try:
        pos, opts = parse(argv[2:])
    except StopIteration:
        print(__doc__)
        return 3
    replay = opts.get("--replay")
    if replay and not os.path.exists(replay):
        print("replay missing: %s" % replay)
        return 2
    # absolute: run_mame.sh changes into MAME's work directory
    work = os.path.abspath(opts.get("--work") or tempfile.mkdtemp(prefix="arcade-gate-"))
    os.makedirs(work, exist_ok=True)
    keep = "--work" in opts
    try:
        if cmd == "z80steps" and len(pos) == 1:
            return z80steps(pos[0], work)
        if len(pos) != 2 or pos[0] not in SETS or not pos[1].isdigit():
            print(__doc__)
            return 3
        setname, frames = pos[0], int(pos[1])
        if cmd == "determinism":
            return determinism(setname, frames, replay, work)
        if cmd == "lockstep":
            mode = opts.get("--stage-m", "stock")
            if mode not in STAGE_M_MODES[setname]:
                print("lockstep: --stage-m for %s: %s" % (setname, " or ".join(STAGE_M_MODES[setname])))
                return 3
            fields = opts["--fields"].split(",") if "--fields" in opts else None
            if fields is None and not opts.get("--img"):
                fields = [f for f in A.SETS[setname]["fields"] if f != "img"]
            return lockstep(setname, frames, opts.get("--headless"), replay, work, bool(opts.get("--img")),
                            mode, fields, opts["--skip-field"])
        print(__doc__)
        return 3
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
