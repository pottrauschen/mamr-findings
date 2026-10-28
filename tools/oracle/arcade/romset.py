#!/usr/bin/env python3
"""Prepare a MAME ROM path for an arcade set from loose files.

    romset.py prepare ROMPATH SET ROMDIR [--mame EXE]
        asks MAME (`-listroms SET`) for the file names and SHA-1 of the
        set, finds each file in ROMDIR by its MAME name or by SHA-1, and
        links it as ROMPATH/SET/<MAME name>. Files MAME lists as "NO GOOD
        DUMP KNOWN" are skipped. Exit 2 when MAME or a file is missing.
    romset.py selftest

The sets circulate with older file names (the Ikari set of the repository
uses 1.rom ... 20.rom), and MAME finds loose files only under its own
names, hence the links. Nothing is copied.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys

LINE = re.compile(r"^(\S+)\s+(\d+)\s+CRC\(([0-9a-f]{8})\)\s+SHA1\(([0-9a-f]{40})\)")


def parse_listroms(text):
    """[(name, size, crc, sha1)] of the files with a known dump."""
    out = []
    for line in text.splitlines():
        m = LINE.match(line.strip())
        if m:
            out.append((m.group(1), int(m.group(2)), m.group(3), m.group(4)))
    return out


def sha1_of(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def prepare(rompath, setname, romdir, mame):
    exe = shutil.which(mame) if not os.path.isabs(mame) else mame
    if not exe or not os.path.exists(exe):
        print("romset.py: MAME not found (%s)" % mame, file=sys.stderr)
        return 2
    if not os.path.isdir(romdir):
        print("romset.py: no ROM directory %s" % romdir, file=sys.stderr)
        return 2
    res = subprocess.run([exe, "-listroms", setname], capture_output=True, text=True)
    want = parse_listroms(res.stdout)
    if not want:
        print("romset.py: MAME lists no ROMs for %s" % setname, file=sys.stderr)
        return 2
    by_sha = {}
    for name in sorted(os.listdir(romdir)):
        p = os.path.join(romdir, name)
        if os.path.isfile(p):
            by_sha.setdefault(sha1_of(p), p)
    dst = os.path.join(rompath, setname)
    os.makedirs(dst, exist_ok=True)
    missing = []
    for name, _size, _crc, sha in want:
        src = os.path.join(romdir, name)
        if not (os.path.isfile(src) and sha1_of(src) == sha):
            src = by_sha.get(sha)
        if not src:
            missing.append(name)
            continue
        link = os.path.join(dst, name)
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(os.path.abspath(src), link)
    if missing:
        print("romset.py: %s: missing %s" % (setname, " ".join(missing)), file=sys.stderr)
        return 2
    return 0


def selftest():
    text = ("ROMs required for driver \"x\".\nName  Size Checksum\n"
            "1.4p   65536 CRC(52a8b2dd) SHA1(a896387d68ed9a55c313bdb81acdf8d68b7a1264)\n"
            "1.1d    4096 NO GOOD DUMP KNOWN\n")
    got = parse_listroms(text)
    ok = got == [("1.4p", 65536, "52a8b2dd", "a896387d68ed9a55c313bdb81acdf8d68b7a1264")]
    print("romset selftest: %s" % ("ok" if ok else "FAILED %r" % got))
    return 0 if ok else 1


def main(argv):
    if len(argv) >= 2 and argv[1] == "selftest":
        return selftest()
    if len(argv) >= 5 and argv[1] == "prepare":
        mame = "mame"
        if len(argv) == 7 and argv[5] == "--mame":
            mame = argv[6]
        elif len(argv) != 5:
            print(__doc__)
            return 3
        return prepare(argv[2], argv[3], argv[4], mame)
    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(main(sys.argv))
