#!/usr/bin/env python3
"""Prepare a MAME ROM path for the set spang from spang-set.toml.

    romset.py prepare ROMPATH ROMDIR [--ym2413 FILE] [--manifest TOML]
        ROMPATH/spang/<MAME name>: a symbolic link to every file of the
        manifest, found in ROMDIR by name or by size and SHA-1 (the set
        circulates with older names, and MAME only finds loose files by
        their MAME names); ROMPATH/ym2413/ym2413_instruments.bin: a copy of
        FILE (a dump of the chip's instrument ROM) or, without it, the
        placeholder from the vendored ymfm (hashline.py placeholder).
        Prints "ym2413=rom" or "ym2413=placeholder". Exit 2 when a file
        is missing (the oracle tests count that as skipped).
    romset.py selftest

Exit codes: 0 success, 1 failure, 2 ROM set incomplete, 3 usage error.
"""
import hashlib
import os
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True  # no __pycache__ in the source tree
import hashline as H  # noqa: E402

DEFAULT_MANIFEST = os.path.join(HERE, "spang-set.toml")


def manifest_files(path):
    """(name, size, sha1) of every file the manifest lists, once each."""
    with open(path, "rb") as f:
        t = tomllib.load(f)
    seen, out = set(), []
    entries = []
    for cpu in t.get("cpu", []):
        entries += cpu.get("files", [])
    for reg in t.get("region", []):
        entries += reg.get("files", [])
    for e in entries:
        if e["file"] in seen:
            continue
        seen.add(e["file"])
        out.append((e["file"], e["size"], e["sha1"]))
    return out


def sha1_of(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def find(romdir, name, size, sha1):
    p = os.path.join(romdir, name)
    if os.path.isfile(p) and os.path.getsize(p) == size and sha1_of(p) == sha1:
        return p
    try:
        entries = sorted(os.listdir(romdir))
    except OSError:
        return None
    for e in entries:
        q = os.path.join(romdir, e)
        if os.path.isfile(q) and os.path.getsize(q) == size and sha1_of(q) == sha1:
            return q
    return None


def prepare(rompath, romdir, ym2413=None, manifest=DEFAULT_MANIFEST, out=print):
    setdir = os.path.join(rompath, "spang")
    ymdir = os.path.join(rompath, "ym2413")
    os.makedirs(setdir, exist_ok=True)
    os.makedirs(ymdir, exist_ok=True)
    missing = []
    for name, size, sha1 in manifest_files(manifest):
        src = find(romdir, name, size, sha1)
        dst = os.path.join(setdir, name)
        if os.path.lexists(dst):
            os.remove(dst)
        if src is None:
            missing.append(name)
            continue
        os.symlink(os.path.abspath(src), dst)
    if missing:
        out("romset: missing in %s: %s" % (romdir, " ".join(missing)))
        return 2
    target = os.path.join(ymdir, "ym2413_instruments.bin")
    if ym2413:
        with open(ym2413, "rb") as f:
            data = f.read()
        kind = "rom"
    else:
        data = H.ymfm_default_instruments(H.default_ymfm_path())
        kind = "placeholder"
    with open(target, "wb") as f:
        f.write(data)
    out("ym2413=%s" % kind)
    return 0


def selftest():
    import tempfile
    files = manifest_files(DEFAULT_MANIFEST)
    names = [f[0] for f in files]
    assert len(files) == 11, names
    assert "spe_06.11h" in names and "eeprom-spang.bin" in names
    with tempfile.TemporaryDirectory() as td:
        romdir = os.path.join(td, "roms")
        os.mkdir(romdir)
        # a set with nothing in it is incomplete
        assert prepare(os.path.join(td, "rp"), romdir, out=lambda s: None) == 2
        # a file found by content under another name
        data = b"spang selftest"
        sha = hashlib.sha1(data).hexdigest()
        with open(os.path.join(romdir, "old.rom"), "wb") as f:
            f.write(data)
        assert find(romdir, "new.11h", len(data), sha) == os.path.join(romdir, "old.rom")
        assert find(romdir, "new.11h", len(data) + 1, sha) is None
    print("romset selftest ok")
    return 0


def main(argv):
    if len(argv) >= 2 and argv[1] == "selftest":
        return selftest()
    if len(argv) >= 4 and argv[1] == "prepare":
        args = argv[2:]
        ym, manifest = None, DEFAULT_MANIFEST
        if "--ym2413" in args:
            i = args.index("--ym2413")
            ym = args[i + 1] or None
            args = args[:i] + args[i + 2:]
        if "--manifest" in args:
            i = args.index("--manifest")
            manifest = args[i + 1]
            args = args[:i] + args[i + 2:]
        return prepare(args[0], args[1], ym, manifest)
    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
