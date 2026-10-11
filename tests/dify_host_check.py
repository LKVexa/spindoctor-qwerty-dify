#!/usr/bin/env python3
# SpinDoctor Qwerty for Dify 1.1.0 - host check (static checks + the real Dify plugin runtime)
# Copyright (C) 2026 RUSSELL PHILIP SMITHSON <russellsmithson77@outlook.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. It is distributed WITHOUT ANY WARRANTY; see the LICENSE file for details.
"""Run with the Python that has requirements.txt installed (the dify_plugin SDK, which also brings PyYAML):

  .venv/bin/python tests/dify_host_check.py --cli ./dify-plugin [--out tests/host_check.json]

Static: manifest/provider/tool YAML, engine parity of the tool list, GPL headers, deterministic packaging (official
CLI twice + the built-in packer, same file contents), package contents; SDK: the glue's argument conversion and error
paths. Real host: `dify plugin package`, then `dify plugin run` (the official daemon's local runtime, no Dify server,
no login) drives every tool through tests/e2e_mcp.py via tests/dify_bridge.py, plus uploads for q.folder ($FILES)
and error handling. Standard library + the SDK's own dependencies only.
"""
import glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile, zipfile
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
R = []


def T(name, ok, detail=""):
    R.append({"check": name, "pass": bool(ok), "detail": str(detail)[:500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -- " + str(detail)[:400])); sys.stdout.flush()


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    a = sys.argv[1:]; opt = dict(zip(a[::2], a[1::2]))
    cli = opt.get("--cli") or os.environ.get("DIFY_CLI") or shutil.which("dify") or shutil.which("dify-plugin")
    cli = os.path.abspath(cli) if cli else None
    outp = opt.get("--out", os.path.join(HERE, "host_check.json"))
    import yaml
    from spindoctor import api
    # 1. manifest
    m = yaml.safe_load(open(os.path.join(ROOT, "manifest.yaml"), encoding="utf-8"))
    req = ("version", "type", "author", "name", "label", "description", "icon", "resource", "plugins", "meta", "created_at")
    T("manifest.yaml: required fields, version 1.1.0, type plugin, Python 3.12 runner, entrypoint main",
      all(k in m for k in req) and m["version"] == "1.1.0" and m["type"] == "plugin" and m["meta"]["runner"] == {"language": "python", "version": "3.12", "entrypoint": "main"}
      and re.fullmatch(r"[a-z0-9_-]{1,64}", m["author"]) and re.fullmatch(r"[a-z0-9_-]{1,128}", m["name"]) and os.path.isfile(os.path.join(ROOT, "_assets", m["icon"])), m)
    # 2. provider + tools vs engine
    prov = yaml.safe_load(open(os.path.join(ROOT, m["plugins"]["tools"][0]), encoding="utf-8"))
    eng = {t["name"]: t for t in api.TOOLS}; names = []; problems = []
    for rel in prov["tools"]:
        d = yaml.safe_load(open(os.path.join(ROOT, rel), encoding="utf-8")); n = d["identity"]["name"]; names.append(n)
        if not os.path.isfile(os.path.join(ROOT, d["extra"]["python"]["source"])): problems.append(n + ": source missing")
        llm = {p["name"] for p in d["parameters"] if p["form"] == "llm"}
        want = set(eng.get(n, {}).get("parameters", {}).get("properties", {})) - {"workspace"}
        if n == "spindoctor_test_theory": want = want - {"path"} | {"file"}
        if not want <= llm | {"path"}: problems.append(n + " missing " + str(sorted(want - llm)))
        for p in d["parameters"]:
            if p["type"] == "select" and not p.get("options"): problems.append(n + "." + p["name"] + " select without options")
            if p["form"] not in ("llm", "form"): problems.append(n + "." + p["name"] + " bad form")
    T("provider: 6 tools named exactly like the engine (function table matches), every engine parameter exposed", sorted(names) == sorted(eng) and not problems and os.path.isfile(os.path.join(ROOT, prov["extra"]["python"]["source"])), problems or names)
    srcs = [p for p in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True) + glob.glob(os.path.join(ROOT, "**", "*.yaml"), recursive=True) if "/." not in p]
    nohdr = [os.path.relpath(p, ROOT) for p in srcs if "SPDX-License-Identifier: GPL-3.0-or-later" not in open(p, encoding="utf-8").read(2000)]
    T("GPL-3.0-or-later SPDX header in every .py/.yaml (%d files)" % len(srcs), not nohdr, nohdr)
    T("requirements.txt pins the current dify_plugin SDK line (>=0.10.2,<0.11.0)", open(os.path.join(ROOT, "requirements.txt")).read().strip() == "dify_plugin>=0.10.2,<0.11.0")
    # 3. glue argument conversion (real SDK import)
    from tools import _engine as g
    import dify_plugin  # noqa: F401
    a1, _, e1, _ = g.prepare("spindoctor_run_preset", {"preset_id": "qc-001", "overrides": "shots=64 basis=x"})
    _, _, e2, _ = g.prepare("spindoctor_run_preset", {"preset_id": "qc-001", "overrides": "shots"})
    _, _, e3, _ = g.prepare("spindoctor_test_theory", {"checks": "[{bad"})
    _, _, e4, _ = g.prepare("spindoctor_run_script", {"script": 'q.folder run path="$FILES"'})
    a5, _, _, at = g.prepare("spindoctor_test_theory", {"excerpts": "User: a\n\nAssistant: b", "checks": '{"kind":"ok","command":1}', "attach_reports": False})
    a6, _, _, _ = g.prepare("spindoctor_functions", {"workspace": "/x"})
    T("glue: overrides/checks/excerpts conversion, clear errors for bad overrides, bad checks JSON, $FILES without uploads",
      not e1 and a1["overrides"] == {"shots": "64", "basis": "x"} and "name=value" in (e2 or "") and "JSON" in (e3 or "") and "no files" in (e4 or "")
      and a5["excerpts"] == ["User: a", "Assistant: b"] and a5["checks"] == [{"kind": "ok", "command": 1}] and at is False and "workspace" not in a6, [e1, e2, e3, e4])
    # 4. packaging
    b = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_difypkg.py"), "--builtin", "--check", "--out", os.path.join(tempfile.gettempdir(), "sdq-builtin.difypkg")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    T("built-in packer is deterministic (two builds, identical bytes)", b.returncode == 0 and b"deterministic: yes" in b.stdout, b.stdout[-400:])
    if not cli:
        T("official Dify CLI available (dify-plugin binary; pass --cli)", False, "not found")
        return finish(outp)
    ver = subprocess.run([cli, "version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode().strip()
    pkg = os.path.join(ROOT, "dist", "spindoctor_qwerty-1.1.0.difypkg")
    c = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_difypkg.py"), "--cli", cli, "--check"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    T("official `dify plugin package` (CLI %s) validates and packs deterministically" % ver, c.returncode == 0 and b"deterministic: yes" in c.stdout and os.path.isfile(pkg), c.stdout[-600:])
    zc, zb = zipfile.ZipFile(pkg), zipfile.ZipFile(os.path.join(tempfile.gettempdir(), "sdq-builtin.difypkg"))
    same = zc.namelist() == zb.namelist() and all(zc.read(n) == zb.read(n) for n in zc.namelist())
    names = zc.namelist()
    T("package: CLI and built-in packer hold identical files; no tests/scripts/examples/.git; engine + 6 tools inside (%d files)" % len(names),
      same and not [n for n in names if n.split("/")[0] in ("tests", "scripts", "examples", "dist", ".git", ".github")] and "spindoctor/api.py" in names
      and len([n for n in names if n.startswith("tools/spindoctor_") and n.endswith(".yaml")]) == 6 and "LICENSE" in names, [n for n in names if "/" not in n])
    os.remove(os.path.join(tempfile.gettempdir(), "sdq-builtin.difypkg"))
    kd = tempfile.mkdtemp(prefix="sdq-key-")  # throwaway key pair, deleted right after
    subprocess.run([cli, "signature", "generate", "-f", "throwaway"], cwd=kd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    sg = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_difypkg.py"), "--cli", cli, "--sign", os.path.join(kd, "throwaway.private.pem"), "--out", os.path.join(kd, "p.difypkg")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    vf = subprocess.run([cli, "signature", "verify", os.path.join(kd, "p.signed.difypkg"), "-p", os.path.join(kd, "throwaway.public.pem")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    T("optional signing: build --sign (category community) then `dify signature verify` with the public key", sg.returncode == 0 and vf.returncode == 0, (sg.stdout + vf.stdout)[-500:])
    shutil.rmtree(kd, ignore_errors=True)
    # 5. real runtime: shared E2E through the bridge
    stats = os.path.join(tempfile.mkdtemp(prefix="sdq-stats-"), "s.json"); env = dict(os.environ, SDQ_BRIDGE_STATS=stats)
    bridge = [sys.executable, os.path.join(HERE, "dify_bridge.py"), "--cli", cli, "--package", pkg]
    e2e_out = os.path.join(HERE, "e2e_results.json")
    r = subprocess.run([sys.executable, os.path.join(HERE, "e2e_mcp.py"), "--server"] + bridge + ["--examples", os.path.join(ROOT, "examples", "theory"), "--out", e2e_out], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=3600)
    txt = r.stdout.decode("utf-8", "replace"); summ = re.search(r"SUMMARY (\d+)/(\d+)", txt)
    T("real Dify runtime (`dify plugin run`): shared E2E %s (tools, function table, every family, 298q, q.folder, theory file/chat/transcript, presets vs 3.1.2 reference, PDFs)" % (summ.group(0) if summ else "?"),
      r.returncode == 0 and summ and summ.group(1) == summ.group(2), "\n".join(l for l in txt.splitlines() if l.startswith("FAIL"))[-800:])
    # 6. uploads for q.folder + error paths through the runtime
    tmp = tempfile.mkdtemp(prefix="sdq-up-"); fd = os.path.join(tmp, "upload")
    os.makedirs(fd)
    open(os.path.join(fd, "a_steps.txt"), "w").write("q.circuit new up 2\nq.circuit add h 0\nq.circuit add cx 0 1\nq.circuit run shots 64 basis z\n")
    open(os.path.join(fd, "b_ghz.qasm"), "w").write('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[3];\ncreg c[3];\nh q[0];\ncx q[0],q[1];\ncx q[1],q[2];\nmeasure q -> c;\n')
    open(os.path.join(fd, "c_notes.md"), "w").write("# skipped by q.folder\n")
    p = subprocess.Popen(bridge + ["--files-dir", fd], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=dict(env, SPINDOCTOR_WORKSPACE=os.path.join(tmp, "ws")))
    def rpc(i, method, params):
        p.stdin.write((json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params}) + "\n").encode()); p.stdin.flush()
        return json.loads(p.stdout.readline())
    rpc(1, "initialize", {})
    up = rpc(2, "tools/call", {"name": "spindoctor_run_script", "arguments": {"script": 'q.folder run path="$FILES" downloads=false verify=false'}})["result"]["structuredContent"]
    job = ((up.get("results") or [{}])[0].get("result") or {}); job = job.get("job") or job
    T("uploaded files -> $FILES -> q.folder run completes (2 command files, .md skipped)", up.get("ok") and job.get("phase") == "completed" and len(job.get("files", [])) == 2 and job.get("skippedFiles") == ["c_notes.md"], {k: job.get(k) for k in ("phase", "error", "skippedFiles")} or up.get("error"))
    bad1 = rpc(3, "tools/call", {"name": "spindoctor_run_preset", "arguments": {"preset_id": "qc-999"}})["result"]["structuredContent"]
    bad2 = rpc(4, "tools/call", {"name": "spindoctor_test_theory", "arguments": {"source": "text", "text": "x", "hypothesis": "h", "prediction": "p", "checks": "[{oops"}})["result"]["structuredContent"]
    bad3 = rpc(5, "tools/call", {"name": "spindoctor_report", "arguments": {"name": "../../etc/passwd"}})["result"]["structuredContent"]
    T("errors come back as ok=false with a clear message (unknown preset, bad checks JSON, report path escape)",
      not bad1.get("ok") and bad1.get("error") and not bad2.get("ok") and "JSON" in str(bad2.get("error")) and not bad3.get("ok") and "inside" in str(bad3.get("error")), [bad1.get("error"), bad2.get("error"), bad3.get("error")])
    p.stdin.close(); p.wait(60); shutil.rmtree(tmp, ignore_errors=True)
    st = json.load(open(stats)); shutil.rmtree(os.path.dirname(stats), ignore_errors=True)
    tot = {k: sum(s[k] for s in st) for k in ("calls", "blobs", "pdfBlobs", "txtBlobs", "badBlobs", "fileUploads")}
    T("report files attached as Dify blobs (%(pdfBlobs)d PDF + %(txtBlobs)d TXT over %(calls)d calls, %(fileUploads)d uploads), all valid" % tot,
      tot["pdfBlobs"] >= 10 and tot["badBlobs"] == 0 and tot["fileUploads"] >= 4, tot)
    left = subprocess.run(["pgrep", "-f", "plugin run " + pkg], stdout=subprocess.PIPE).stdout.decode().split() if shutil.which("pgrep") else []
    T("no plugin runtime left running", not left, left)
    return finish(outp)


def finish(outp):
    json.dump({"passed": sum(r["pass"] for r in R), "total": len(R), "python": sys.version.split()[0], "checks": R}, open(outp, "w"), indent=1)
    print("HOST CHECK %d/%d passed" % (sum(r["pass"] for r in R), len(R)))
    return 0 if all(r["pass"] for r in R) else 1


if __name__ == "__main__":
    sys.exit(main())
