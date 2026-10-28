#!/usr/bin/env python3
"""Super Pang oracle gates (docs/spang-oracles.md section 5).

    gates.py determinism FRAMES [--input SCRIPT] [--work DIR]
        two MAME runs of FRAMES frames each must be byte-identical
    gates.py lockstep FRAMES --headless EXE [--input SCRIPT] [--work DIR]
            [--fields LIST] [--skip-frames LIST] [--skip-field F:LIST]
            [--img] [--iolog] [--eeprom-set OFFSET=VALUE,...]
        one MAME run and one spang_headless run of the same frames and
        input script; compare.py lines over the given fields (default: all
        but img; --img adds the picture, MAME then draws every frame,
        about ten times the run time). --skip-field excludes frames of one
        field from the verdict (compare.py). With --iolog both sides write
        their I/O logs and the first differing access is printed as well.
        --eeprom-set starts both sides from the set's default EEPROM with
        the given bytes replaced (byte offsets into the 128-byte image,
        e.g. "2=1": the screen flip setting, docs/spang-oracles.md);
        SPANG_EEPROM for MAME, --eeprom for spang_headless.
    gates.py audio FRAMES --headless EXE [--input SCRIPT] [--work DIR]
        MAME's recorded sound (-wavwrite) against spang_headless --wav over
        the same frames: audio.py compare, a plausibility check of the
        level curves, not of the samples (docs/spang-oracles.md section 9)
    gates.py native FRAMES --headless EXE [--input SCRIPT] [--eeprom-set ...]
        spang_headless with its recompiled blocks against itself with
        --interpret (no MAME): the hash files must be byte-identical (every
        field, zclk, the picture) and the native run's miss log empty
        (docs/spang-oracles.md section 10)
    gates.py views ROMTOOL [--no-mame] [--work DIR]
        the Kabuki views three ways: romtool --dump-views, the reference
        implementation kabuki.py, and MAME's own decrypted address spaces
        (views_mame.lua); all must be byte-identical. --no-mame leaves out
        the MAME part (needs only the ROM set).
    gates.py selftest

The runs go through run_mame.sh (MAME, MAME_WORK, SPANG_ROMS, SPANG_YM2413
as there). Exit codes: 0 pass, 1 fail, 2 skipped (MAME, ROM set or
headless runner missing), 3 usage error.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True  # no __pycache__ in the source tree
import audio as A  # noqa: E402
import compare as C  # noqa: E402
import hashline as H  # noqa: E402
import romset as R  # noqa: E402

LOCKSTEP_FIELDS = ["z80", "wram", "vram", "obj", "pal", "bank", "irq", "eep", "ym", "oki"]


def run_mame(out, frames, script=None, iolog=None, env_extra=None):
    env = dict(os.environ)
    env.pop("FH_IMG", None)
    if script:
        env["FH_INPUT"] = os.path.abspath(script)
    if iolog:
        env["FH_IOLOG"] = iolog
    env.update(env_extra or {})
    # a private MAME directory per run: two gates may run at the same time
    env["MAME_WORK"] = out + ".mamework"
    t0 = time.time()
    r = subprocess.run(["sh", os.path.join(HERE, "run_mame.sh"), out, str(frames)], env=env)
    print("MAME run: %d frames, exit %d, %.1f s" % (frames, r.returncode, time.time() - t0))
    return r.returncode


def determinism(frames, script, work):
    a, b = os.path.join(work, "a.hash"), os.path.join(work, "b.hash")
    for p in (a, b):
        rc = run_mame(p, frames, script)
        if rc != 0:
            return 2 if rc == 2 else 1
    if not H.verify_file(a, frames):
        return 1
    with open(a, "rb") as fa, open(b, "rb") as fb:
        same = fa.read() == fb.read()
    print("determinism: %s" % ("byte-identical" if same else "DIFFERENT"))
    if not same:
        C.compare_lines(a, b)
    return 0 if same else 1


def patched_eeprom(spec, work):
    """The set's EEPROM default with the bytes of "OFF=VAL,..." replaced,
    written to WORK/eeprom.bin; None when the set has no EEPROM file."""
    roms = os.environ.get("SPANG_ROMS") or os.path.join(HERE, "..", "..", "..", "roms", "spang")
    for name, size, sha1 in R.manifest_files(R.DEFAULT_MANIFEST):
        if name.startswith("eeprom"):
            src = R.find(roms, name, size, sha1)
            break
    else:
        src = None
    if not src:
        return None
    data = bytearray(open(src, "rb").read())
    for part in spec.split(","):
        off, val = part.split("=")
        data[int(off, 0)] = int(val, 0)
    path = os.path.join(work, "eeprom.bin")
    with open(path, "wb") as f:
        f.write(bytes(data))
    return path


def lockstep(frames, exe, script, work, fields, skip, iolog, img=False, skip_fields=None, eeprom=None):
    if not exe or not os.path.exists(exe):
        print("lockstep: headless runner missing: %s" % exe)
        return 2
    m, h = os.path.join(work, "mame.hash"), os.path.join(work, "mamr.hash")
    mio = os.path.join(work, "mame.io") if iolog else None
    hio = os.path.join(work, "mamr.io") if iolog else None
    extra = {"FH_IMG": "1"} if img else {}
    if eeprom:
        extra["SPANG_EEPROM"] = eeprom
    rc = run_mame(m, frames, script, mio, extra)
    if rc != 0:
        return 2 if rc == 2 else 1
    cmd = [exe, "--frames", str(frames), "--out", h]
    if not img:
        cmd += ["--no-img"]
    if eeprom:
        cmd += ["--eeprom", eeprom]
    if script:
        cmd += ["--input", os.path.abspath(script)]
    if hio:
        cmd += ["--iolog", hio]
    t0 = time.time()
    r = subprocess.run(cmd)
    print("spang_headless: exit %d, %.1f s" % (r.returncode, time.time() - t0))
    if r.returncode == 2:
        return 2
    if r.returncode != 0:
        return 1
    if img and "img" not in fields:
        fields = fields + ["img"]
    eq, _ = C.compare_lines(m, h, fields, True, frames, skip, skip_fields=skip_fields)
    if iolog and not eq:
        C.compare_iolog(mio, hio)
    return 0 if eq else 1


def audio(frames, exe, script, work):
    if not exe or not os.path.exists(exe):
        print("audio: headless runner missing: %s" % exe)
        return 2
    m, h = os.path.join(work, "mame.wav"), os.path.join(work, "mamr.wav")
    rc = run_mame(os.path.join(work, "mame.hash"), frames, script, env_extra={"SPANG_WAV": m})
    if rc != 0:
        return 2 if rc == 2 else 1
    cmd = [exe, "--frames", str(frames), "--out", os.path.join(work, "mamr.hash"), "--no-img", "--wav", h]
    if script:
        cmd += ["--input", os.path.abspath(script)]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        return 2 if r.returncode == 2 else 1
    return 0 if A.compare(m, h) else 1


def native(frames, exe, script, work, eeprom=None):
    if not exe or not os.path.exists(exe):
        print("native: headless runner missing: %s" % exe)
        return 2
    base = [exe, "--frames", str(frames)]
    if script:
        base += ["--input", os.path.abspath(script)]
    if eeprom:
        base += ["--eeprom", eeprom]
    n, i, miss = (os.path.join(work, x) for x in ("native.hash", "interp.hash", "miss.txt"))
    for cmd in (base + ["--out", n, "--miss-log", miss], base + ["--out", i, "--interpret"]):
        t0 = time.time()
        r = subprocess.run(cmd)
        print("%s: exit %d, %.1f s" % (" ".join(os.path.basename(x) for x in cmd[:1] + cmd[-2:]), r.returncode,
                                       time.time() - t0))
        if r.returncode != 0:
            return 2 if r.returncode == 2 else 1
    with open(n, "rb") as fa, open(i, "rb") as fb:
        same = fa.read() == fb.read()
    with open(miss) as f:
        misses = [x for x in f if x.strip()]
    print("native: %s, %d misses" % ("byte-identical to the interpreter" if same else "DIFFERENT", len(misses)))
    for x in misses[:20]:
        print("  miss " + x.rstrip())
    if not same:
        C.compare_lines(i, n)
    return 0 if same and not misses else 1


def views(romtool, work, with_mame):
    roms = os.environ.get("SPANG_ROMS") or os.path.join(HERE, "..", "..", "..", "roms", "spang")
    manifest = R.DEFAULT_MANIFEST
    if not os.path.isdir(roms):
        print("views: no ROM set in %s" % roms)
        return 2
    rt, py, mm = (os.path.join(work, x) for x in ("romtool", "python", "mame"))
    r = subprocess.run([romtool, manifest, roms, "--dump-views", rt])
    if r.returncode != 0:
        return 2 if not os.path.exists(os.path.join(roms, "..")) else 1
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "kabuki.py"), "views", roms, py])
    if r.returncode != 0:
        return r.returncode
    ok = subprocess.run([sys.executable, "-I", os.path.join(HERE, "kabuki.py"), "compare", rt, py]).returncode == 0
    if with_mame:
        rc = run_mame(os.path.join(work, "views.unused"), 1, env_extra={"FH_VIEWS": mm})
        if rc != 0:
            return 2 if rc == 2 else 1
        ok = subprocess.run([sys.executable, "-I", os.path.join(HERE, "kabuki.py"), "compare", rt, mm,
                             "--mame"]).returncode == 0 and ok
    print("views: %s" % ("byte-identical" if ok else "DIFFERENT"))
    return 0 if ok else 1


def main(argv):
    if len(argv) >= 2 and argv[1] == "selftest":
        assert set(LOCKSTEP_FIELDS) < set(H.FIELDS)
        print("gates selftest ok")
        return 0
    if len(argv) < 3 or argv[1] not in ("determinism", "lockstep", "audio", "native", "views"):
        print(__doc__)
        return 3
    args = argv[3:]

    def opt(name):
        if name in args:
            i = args.index(name)
            v = args[i + 1]
            del args[i:i + 2]
            return v
        return None
    script, work, exe = opt("--input"), opt("--work"), opt("--headless")
    fields = opt("--fields")
    skip = C.parse_frames(opt("--skip-frames"))
    field_skips = []
    while "--skip-field" in args:
        field_skips.append(opt("--skip-field"))
    iolog = "--iolog" in args
    img = "--img" in args
    eeprom_set = opt("--eeprom-set")
    if argv[1] == "views":
        tmp = None if work else tempfile.mkdtemp(prefix="spang-views-")
        try:
            return views(argv[2], work or tmp, "--no-mame" not in args)
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)
    frames = int(argv[2])
    tmp = None
    if not work:
        tmp = tempfile.mkdtemp(prefix="spang-gate-")
        work = tmp
    os.makedirs(work, exist_ok=True)
    try:
        if argv[1] == "determinism":
            return determinism(frames, script, work)
        if argv[1] == "audio":
            return audio(frames, exe, script, work)
        eeprom = None
        if eeprom_set:
            eeprom = patched_eeprom(eeprom_set, work)
            if not eeprom:
                print("lockstep: no EEPROM file in the ROM set")
                return 2
        if argv[1] == "native":
            return native(frames, exe, script, work, eeprom)
        return lockstep(frames, exe, script, work,
                        fields.split(",") if fields else LOCKSTEP_FIELDS, skip, iolog, img,
                        C.parse_field_skips(field_skips), eeprom)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
