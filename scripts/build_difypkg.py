#!/usr/bin/env python3
# SpinDoctor Qwerty for Dify 1.1.0 - deterministic .difypkg builder
# Copyright (C) 2026 RUSSELL PHILIP SMITHSON <russellsmithson77@outlook.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. It is distributed WITHOUT ANY WARRANTY; see the LICENSE file for details.
"""Build dist/spindoctor_qwerty-1.1.0.difypkg from this repository.

  python3 scripts/build_difypkg.py              # official Dify CLI if found, else the built-in packer
  python3 scripts/build_difypkg.py --cli PATH   # use this Dify CLI binary (dify-plugin-<os>-<arch>)
  python3 scripts/build_difypkg.py --builtin    # standard-library packer only (no Dify CLI needed)
  python3 scripts/build_difypkg.py --check      # build twice and confirm identical bytes, print the file list
  python3 scripts/build_difypkg.py --cli PATH --sign my_key.private.pem   # also write ...signed.difypkg (category community)

The official CLI (`dify plugin package`, from github.com/langgenius/dify-plugin-daemon releases) validates the manifest
and writes a zip with files sorted by path and no timestamps, so the same sources always give the same bytes.
The built-in packer selects the SAME files (the .difyignore rules this repo uses) and writes them sorted with a fixed
1980-01-01 timestamp, so it is deterministic too; its bytes differ from the CLI's (different deflate), the contents
do not. Standard library only (Python 3.8+); no network access.
"""
import argparse, fnmatch, hashlib, os, shutil, subprocess, sys, tempfile, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "spindoctor_qwerty-1.1.0.difypkg"


def ignore_rules():
    rules = []
    with open(os.path.join(ROOT, ".difyignore"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                rules.append(line)
    return rules


def ignored(parts, is_dir, rules):
    """The subset of gitignore matching this repo's .difyignore uses: 'name/' (directory anywhere), 'name' or '*.ext'
    (any path component). Negations and anchored paths are not used here and are rejected."""
    for r in rules:
        if r.startswith("!") or "/" in r.rstrip("/"):
            raise SystemExit("unsupported .difyignore rule for the built-in packer: " + r)
        if r.endswith("/"):
            if any(fnmatch.fnmatchcase(p, r[:-1]) for p in (parts if is_dir else parts[:-1])):
                return True
        elif any(fnmatch.fnmatchcase(p, r) for p in parts):
            return True
    return False


def package_files():
    rules, out = ignore_rules(), []
    for base, dirs, files in os.walk(ROOT):
        rel = os.path.relpath(base, ROOT)
        parts = [] if rel == "." else rel.split(os.sep)
        dirs[:] = sorted(d for d in dirs if not ignored(parts + [d], True, rules))
        for f in files:
            if not ignored(parts + [f], False, rules):
                out.append("/".join(parts + [f]))
    return sorted(out)


def build_builtin(dest):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in package_files():
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3
            with open(os.path.join(ROOT, rel), "rb") as fh:
                z.writestr(info, fh.read())


def find_cli(explicit):
    for c in [explicit, os.environ.get("DIFY_CLI"), shutil.which("dify"), shutil.which("dify-plugin")]:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return os.path.abspath(c)
    return None


def build_cli(cli, dest):
    # Package a pristine copy so stray build/test output in the working tree can never leak in.
    tmp = tempfile.mkdtemp(prefix="sdq-difypkg-")
    try:
        src = os.path.join(tmp, "spindoctor_qwerty")
        os.makedirs(src)
        for rel in package_files() + [".difyignore"]:
            os.makedirs(os.path.dirname(os.path.join(src, rel)), exist_ok=True)
            shutil.copy2(os.path.join(ROOT, rel), os.path.join(src, rel))
        out = os.path.join(tmp, "out.difypkg")
        r = subprocess.run([cli, "plugin", "package", src, "-o", out], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           env=dict(os.environ, HOME=tmp))
        if r.returncode != 0 or not os.path.isfile(out):
            raise SystemExit("dify plugin package failed:\n" + r.stdout.decode("utf-8", "replace")[-2000:])
        shutil.move(out, dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sha256(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cli"); ap.add_argument("--builtin", action="store_true"); ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist", NAME))
    ap.add_argument("--sign", metavar="PRIVATE_PEM", help="sign the package with `dify signature sign -c community` (needs the CLI)")
    a = ap.parse_args()
    cli = None if a.builtin else find_cli(a.cli)
    if a.cli and not cli:
        raise SystemExit("Dify CLI not found or not executable: " + a.cli)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    build = (lambda d: build_cli(cli, d)) if cli else build_builtin
    build(a.out)
    digest = sha256(a.out)
    with zipfile.ZipFile(a.out) as z:
        names = z.namelist()
        bad = z.testzip()
    if bad or "manifest.yaml" not in names or "main.py" not in names:
        raise SystemExit("package is incomplete or corrupt")
    if a.check:
        again = a.out + ".check"
        build(again)
        same = sha256(again) == digest
        os.remove(again)
        print("deterministic:", "yes" if same else "NO")
        for n in names:
            print("  " + n)
        if not same:
            return 1
    print("built %s (%s, %d files, %d bytes)\nsha256 %s" % (a.out, "official Dify CLI" if cli else "built-in packer", len(names), os.path.getsize(a.out), digest))
    if a.sign:
        if not cli:
            raise SystemExit("--sign needs the official Dify CLI (--cli PATH)")
        r = subprocess.run([cli, "signature", "sign", a.out, "-p", os.path.abspath(a.sign), "-c", "community"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        signed = a.out[:-len(".difypkg")] + ".signed.difypkg"
        if r.returncode != 0 or not os.path.isfile(signed):
            raise SystemExit("dify signature sign failed:\n" + r.stdout.decode("utf-8", "replace")[-1500:])
        print("signed %s\nsha256 %s" % (signed, sha256(signed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
