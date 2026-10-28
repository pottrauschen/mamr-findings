#!/usr/bin/env python3
"""Gates of the SNES oracle pipeline (docs/snes-architecture.md section 7).

    gates.py selftest
        the gate logic on synthetic hash files, no oracle needed
    gates.py g2 ORACLE ROM [--frames N]
        run ORACLE twice on ROM; the two outputs must be byte-identical
    gates.py g3 ORACLE ROM [--frames N] [--inject F:ADDR:XOR]
        run ORACLE clean and with one WRAM byte flipped at frame F;
        compare.py must report exactly frame F and field wram
    gates.py cross ROM [--frames N] [--dump-every K]
        aresref against MesenCE: vram, oam and cgram equal in every frame,
        wram equal in the bytes the program defined (mask from fill 00 and
        fill ff runs of both oracles), cycles not compared
    gates.py dumpcheck ORACLE ROM [--frames N] [--dump-every K]
        the writer's hashing against the reference: every dumped frame,
        rehashed by hashline.py, must give the oracle's own F line fields
    gates.py g1 --cmd "COMMAND {out}" [--cmd2 ...]
        MAMR against MAMR: runs COMMAND twice ({out} is replaced by the
        output path) and requires byte-identical hash lines; also usable
        for a stage S / stage E pair with --cmd2
    gates.py reference ORACLE ROM REFERENCE [--frames N]
        the ctest entry, one per oracle: G2 for ORACLE, then aresref equal
        to the checked-in REFERENCE in every field and in mclk, MesenCE
        equal to it in the fields of MESEN_REFERENCE_FIELDS; both files
        must have at least N F lines

ORACLE is aresref or mesence. The oracles are found through the
environment: ARESREF (path of the aresref binary, else "aresref" in PATH)
and MESEN (path of the MesenCE executable, else "Mesen" in PATH; started
through mesen/run_mesen.sh). Work files go to --work DIR (default: a new
temporary directory, removed afterwards unless --keep).

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
import compare  # noqa: E402
import hashline as H  # noqa: E402

SKIP = 2


class Skip(Exception):
    pass


def find_oracle(name):
    if name == "aresref":
        p = os.environ.get("ARESREF") or shutil.which("aresref")
    elif name == "mesence":
        p = os.environ.get("MESEN") or shutil.which("Mesen")
    else:
        raise ValueError("unknown oracle " + name)
    if not p or not os.access(p, os.X_OK):
        raise Skip("%s not found (set %s)" % (name, "ARESREF" if name == "aresref" else "MESEN"))
    return p


def rom_id(rom):
    with open(rom, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def run_oracle(name, rom, out, frames, fill="00", inject=None, dump_dir=None, dump_every=0, ports=False,
               anchors=None, input_script=None):
    """Runs one oracle and returns the wall time in seconds."""
    if not os.path.exists(rom):
        raise Skip("ROM missing: " + rom)
    exe = find_oracle(name)
    t0 = time.time()
    if name == "aresref":
        cmd = [exe, rom, "--frames", str(frames), "--out", out, "--fill", fill, "--rom-id", rom_id(rom)]
        if inject:
            cmd += ["--inject", inject]
        if dump_dir:
            cmd += ["--dump-dir", dump_dir, "--dump-every", str(dump_every)]
        if ports:
            cmd.append("--ports")
        for a in anchors or []:
            cmd += ["--anchor", a]
        if input_script:
            cmd += ["--input", input_script]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("aresref failed (%d): %s" % (r.returncode, r.stderr.strip()))
        check_count(out, frames, "aresref")
    else:
        env = dict(os.environ, MESEN=exe, MESEN_FILL=fill, FH_OUT=os.path.abspath(out), FH_FRAMES=str(frames),
                   FH_ROM_ID=rom_id(rom))
        for k in ("FH_INJECT", "FH_DUMP_DIR", "FH_DUMP_EVERY", "FH_PORTS", "FH_ANCHORS", "FH_INPUT"):
            env.pop(k, None)
        if inject:
            env["FH_INJECT"] = inject
        if dump_dir:
            env["FH_DUMP_DIR"] = os.path.abspath(dump_dir)
            env["FH_DUMP_EVERY"] = str(dump_every)
        if ports:
            env["FH_PORTS"] = "1"
        if anchors:
            env["FH_ANCHORS"] = ",".join(anchors)
        if input_script:
            env["FH_INPUT"] = os.path.abspath(input_script)
        r = subprocess.run([os.path.join(HERE, "mesen", "run_mesen.sh"), os.path.abspath(rom),
                            os.path.join(HERE, "mesen", "snesfh.lua")], env=env, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("MesenCE failed (%d): %s" % (r.returncode, r.stderr.strip()[-500:]))
        check_count(out, frames, "MesenCE")
    return time.time() - t0


def check_count(path, frames, name):
    """The run must have written exactly frames F lines, numbered 1..frames."""
    if not os.path.exists(path):
        raise RuntimeError("%s wrote no output" % name)
    _, recs = H.read_file(path)
    nums = [x["frame"] for x in recs if x["type"] == "F"]
    if nums != list(range(1, frames + 1)):
        raise RuntimeError("%s wrote %d of %d F lines" % (name, len(nums), frames))


def same_bytes(a, b):
    with open(a, "rb") as f:
        x = f.read()
    with open(b, "rb") as f:
        y = f.read()
    return x == y, len(x)


def gate_g2(work, oracle, rom, frames, log):
    p1, p2 = os.path.join(work, oracle + "-run1.hash"), os.path.join(work, oracle + "-run2.hash")
    t1 = run_oracle(oracle, rom, p1, frames, ports=True)
    t2 = run_oracle(oracle, rom, p2, frames, ports=True)
    eq, n = same_bytes(p1, p2)
    log("G2 %s %s: %d frames, %.1f / %.1f s (%.0f fps), %d bytes, %s" % (
        oracle, os.path.basename(rom), frames, t1, t2, frames / max(t1, 1e-9), n,
        "byte-identical" if eq else "DIFFERENT"))
    if not eq:
        compare.compare_lines(p1, p2, timing=True, out=lambda s: log("  " + s))
    return 0 if eq else 1


def check_injection(clean, faulty, frame, log):
    lines = []
    rc = compare.compare_lines(clean, faulty, timing=True, seq=False, out=lines.append)
    for l in lines:
        log("  " + l)
    want = "first divergence: frame %d fields wram" % frame
    ok = rc == 1 and want in lines
    log("G3 %s (expected: %s)" % ("passed" if ok else "FAILED", want))
    return 0 if ok else 1


def gate_g3(work, oracle, rom, frames, inject, log):
    frame = int(inject.split(":")[0])
    clean, faulty = os.path.join(work, oracle + "-clean.hash"), os.path.join(work, oracle + "-fault.hash")
    run_oracle(oracle, rom, clean, frames)
    run_oracle(oracle, rom, faulty, frames, inject=inject)
    log("G3 %s %s: inject %s" % (oracle, os.path.basename(rom), inject))
    return check_injection(clean, faulty, frame, log)


def gate_cross(work, rom, frames, dump_every, log):
    runs = {}
    for oracle in ("aresref", "mesence"):
        for fill in ("00", "ff"):
            d = os.path.join(work, "%s-%s" % (oracle, fill))
            os.makedirs(d, exist_ok=True)
            out = os.path.join(work, "%s-%s.hash" % (oracle, fill))
            t = run_oracle(oracle, rom, out, frames, fill=fill, dump_dir=d, dump_every=dump_every)
            runs[(oracle, fill)] = (out, d)
            log("cross: %s fill %s: %.1f s" % (oracle, fill, t))
    status = 0
    for key, (out, d) in sorted(runs.items()):
        status |= check_dumps(out, d, log)
    a00, m00 = runs[("aresref", "00")][0], runs[("mesence", "00")][0]
    lines = []
    rc = compare.compare_lines(a00, m00, fields=["vram", "oam", "cgram"], seq=False, out=lines.append)
    log("cross: vram/oam/cgram over %d frames: %s" % (frames, "equal" if rc == 0 else "DIFFERENT"))
    for l in lines:
        log("  " + l)
    status |= rc
    lines = []
    compare.compare_lines(a00, m00, out=lines.append)
    log("cross: all fields (informative):")
    for l in lines:
        log("  " + l)
    mask = os.path.join(work, "wram-mask.bin")
    dumped = compare.dump_frames(runs[("aresref", "00")][1], "wram")
    lines = []
    worst = 0
    for fr in dumped:
        lines = []
        rc = compare.make_mask(mask, [(runs[(o, "00")][1], runs[(o, "ff")][1]) for o in ("aresref", "mesence")], fr,
                               out=lines.append)
        if rc:
            return rc
        defined = lines[-1]
        cmp_lines = []
        one = os.path.join(work, "one-a"), os.path.join(work, "one-m")
        for d in one:
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d)
        for src, dst in ((runs[("aresref", "00")][1], one[0]), (runs[("mesence", "00")][1], one[1])):
            shutil.copy(H.dump_path(src, fr, "wram"), H.dump_path(dst, fr, "wram"))
        rc = compare.compare_dumps(one[0], one[1], mask=mask, out=cmp_lines.append)
        worst |= rc
        log("cross: frame %d: %s; %s" % (fr, defined.split(": ", 1)[1], cmp_lines[0].split(": ", 1)[1]))
    log("cross: wram in the defined bytes: %s" % ("equal" if worst == 0 else "DIFFERENT"))
    status |= worst
    lines = []
    compare.compare_dumps(runs[("aresref", "00")][1], runs[("mesence", "00")][1], out=lines.append)
    log("cross: wram unmasked (informative):")
    for l in lines[-4:]:
        log("  " + l)
    return status


def check_dumps(hash_file, dump_dir, log):
    _, recs = H.read_file(hash_file)
    lines = {r["frame"]: r for r in recs if r["type"] == "F"}
    frames = compare.dump_frames(dump_dir, "wram")
    bad = 0
    for fr in frames:
        fields, imgsz = H.load_dump(dump_dir, fr)
        r = H.parse_line(H.format_f(fr, 0, 0, None, fields, imgsz=imgsz)[0])
        miss = [f for f in H.FIELDS + ["imgsz"] if r[f] != lines[fr][f]]
        if miss:
            bad += 1
            log("  frame %d: rehashed dump differs in %s" % (fr, ",".join(miss)))
    log("dumpcheck %s: %d dumped frames rehashed, %s" % (os.path.basename(hash_file), len(frames),
                                                        "all equal" if not bad else "%d differ" % bad))
    return 0 if frames and not bad else 1


def gate_dumpcheck(work, oracle, rom, frames, every, log):
    d = os.path.join(work, oracle + "-dumps")
    os.makedirs(d, exist_ok=True)
    out = os.path.join(work, oracle + "-dumps.hash")
    run_oracle(oracle, rom, out, frames, dump_dir=d, dump_every=every)
    return check_dumps(out, d, log)


def gate_g1(work, cmd1, cmd2, log):
    outs = []
    for i, cmd in enumerate((cmd1, cmd2 or cmd1)):
        out = os.path.join(work, "mamr-run%d.hash" % (i + 1))
        r = subprocess.run(cmd.replace("{out}", shlex.quote(out)), shell=True)
        if r.returncode != 0 or not os.path.exists(out):
            log("G1: command failed: " + cmd)
            return 1
        outs.append(out)
    eq, n = same_bytes(*outs)
    log("G1: %d bytes, %s" % (n, "byte-identical" if eq else "DIFFERENT"))
    if not eq:
        compare.compare_lines(outs[0], outs[1], timing=True, out=lambda s: log("  " + s))
    return 0 if eq else 1


# Fields in which MesenCE must equal the aresref reference files (gilyon
# ROMs, fill 00); see docs/snes-oracles.md for the remaining differences.
MESEN_REFERENCE_FIELDS = ["cpu", "apuio", "wram", "vram", "oam", "cgram", "ppu", "aram", "dsp", "img", "sram"]


def gate_reference(work, oracle, rom, reference, frames, log):
    if not os.path.exists(reference):
        raise Skip("reference missing: " + reference)
    status = gate_g2(work, oracle, rom, frames, log)
    fields = None if oracle == "aresref" else MESEN_REFERENCE_FIELDS
    lines = []
    rc = compare.compare_lines(os.path.join(work, oracle + "-run1.hash"), reference, fields=fields,
                               timing=(oracle == "aresref"), frames=frames, seq=False, out=lines.append)
    log("%s against %s (%s): %s" % (oracle, os.path.basename(reference),
                                    "all fields, mclk" if fields is None else " ".join(fields),
                                    "equal" if rc == 0 else "DIFFERENT"))
    for l in lines:
        log("  " + l)
    return status | rc


def selftest():
    """G2 and G3 decision logic on synthetic data."""
    ok = True
    out = []
    with tempfile.TemporaryDirectory() as d:
        def make(path, fault_frame=None):
            chain = H.FNV_BASIS
            rows = [H.format_header("synthetic", "-")]
            for fr in range(1, 31):
                wram = bytearray(0x20000)
                wram[fr] = 1
                if fault_frame and fr >= fault_frame:
                    wram[0x7F] ^= 0x10
                fields = {f: bytes(H.RAW_FIELDS.get(f, H.FIXED_SIZES.get(f, 4))) for f in H.FIELDS}
                fields["wram"] = bytes(wram)
                line, chain = H.format_f(fr, fr - 1, H.window_mclk(fr), 0x8000, fields, chain, "256x224")
                rows.append(line)
            with open(path, "w") as f:
                f.write("\n".join(rows) + "\n")
        a, b, c, e = (os.path.join(d, x) for x in ("a", "b", "c", "e"))
        make(a)
        make(b)
        make(c, fault_frame=12)
        make(e, fault_frame=13)
        if not same_bytes(a, b)[0]:
            print("FAIL g2 identical")
            ok = False
        if check_injection(a, c, 12, out.append) != 0:
            print("FAIL g3 detects frame 12")
            ok = False
        if check_injection(a, e, 12, out.append) != 1:
            print("FAIL g3 rejects the wrong frame")
            ok = False
        if check_injection(a, b, 12, out.append) != 1:
            print("FAIL g3 rejects a missing fault")
            ok = False
        # Exact frame and field: a fault that also changes another field must fail.
        with open(c) as f:
            text = f.read().replace("F 12 anc=11 mclk=", "F 12 anc=99 mclk=", 1)
        with open(e, "w") as f:
            f.write(text)
        if check_injection(a, e, 12, out.append) != 1:
            print("FAIL g3 rejects extra fields")
            ok = False
        # An oracle run must deliver exactly the requested F lines.
        try:
            check_count(a, 30, "synthetic")
        except RuntimeError:
            print("FAIL count of a complete run")
            ok = False
        for frames, why in ((40, "truncated run"), (29, "longer run")):
            try:
                check_count(a, frames, "synthetic")
                print("FAIL count accepts a " + why)
                ok = False
            except RuntimeError:
                pass
        with open(a) as f:
            text = f.read()
        with open(e, "w") as f:
            f.write("\n".join(l for l in text.split("\n") if not l.startswith("F 7 ")))
        try:
            check_count(e, 30, "synthetic")
            print("FAIL count accepts a missing F line")
            ok = False
        except RuntimeError:
            pass
    if not ok:
        print("\n".join(out))
    print("gates selftest:", "ok" if ok else "FAILED")
    return 0 if ok else 1


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 3
    cmd, rest = argv[1], argv[2:]
    if cmd == "selftest":
        return selftest()
    try:
        pos, o = compare.parse_opts(rest, {"--keep"}, {"--frames", "--inject", "--dump-every", "--work", "--cmd",
                                                       "--cmd2"})
    except ValueError as e:
        print(e, file=sys.stderr)
        return 3
    work = o.get("--work")
    tmp = None
    if not work:
        tmp = tempfile.mkdtemp(prefix="snes-gates-")
        work = tmp
    os.makedirs(work, exist_ok=True)

    def log(s):
        print(s, flush=True)

    try:
        if cmd == "g2" and len(pos) == 2:
            return gate_g2(work, pos[0], pos[1], int(o.get("--frames", "600")), log)
        if cmd == "g3" and len(pos) == 2:
            return gate_g3(work, pos[0], pos[1], int(o.get("--frames", "120")), o.get("--inject", "60:1000:5a"), log)
        if cmd == "cross" and len(pos) == 1:
            return gate_cross(work, pos[0], int(o.get("--frames", "600")), int(o.get("--dump-every", "100")), log)
        if cmd == "dumpcheck" and len(pos) == 2:
            return gate_dumpcheck(work, pos[0], pos[1], int(o.get("--frames", "120")),
                                  int(o.get("--dump-every", "30")), log)
        if cmd == "g1" and "--cmd" in o:
            return gate_g1(work, o["--cmd"], o.get("--cmd2"), log)
        if cmd == "reference" and len(pos) == 3:
            return gate_reference(work, pos[0], pos[1], pos[2], int(o.get("--frames", "300")), log)
        print(__doc__)
        return 3
    except Skip as e:
        log("skip: %s" % e)
        return SKIP
    except RuntimeError as e:
        log("error: %s" % e)
        return 1
    finally:
        if tmp and "--keep" not in o:
            shutil.rmtree(tmp, ignore_errors=True)
        elif "--keep" in o:
            log("work files: " + work)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
