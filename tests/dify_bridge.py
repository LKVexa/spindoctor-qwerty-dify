#!/usr/bin/env python3
# SpinDoctor Qwerty for Dify 1.1.0 - test bridge: MCP stdio front-end over the REAL Dify plugin runtime
# Copyright (C) 2026 RUSSELL PHILIP SMITHSON <russellsmithson77@outlook.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. It is distributed WITHOUT ANY WARRANTY; see the LICENSE file for details.
"""Test harness only (not shipped in the .difypkg).

Starts `dify plugin run <package> -r json` (the official Dify plugin daemon's local runtime: it unpacks the package,
installs requirements.txt with uv, starts main.py under the dify_plugin SDK and speaks the real plugin protocol) and
exposes it as a tiny MCP stdio server, so the shared black-box test (tests/e2e_mcp.py) can drive the plugin's six
Dify tools exactly as Dify would invoke them (type=tool, action=invoke_tool).

  python3 tests/dify_bridge.py --cli <dify-plugin binary> --package dist/spindoctor_qwerty-1.1.0.difypkg [--files-dir DIR]

Argument mapping is what a Dify app would send: lists become one-per-line strings, checks become JSON text, preset
overrides become 'name=value' text. Because the daemon passes only an allow-listed environment to plugins, the
SPINDOCTOR_WORKSPACE / *_SEED variables given to this bridge are applied here: the workspace is sent as the tool's
`workspace` setting, and a NEW workspace is pre-seeded once with the bundled engine (reference reproducibility).
Blob messages (attached TXT/PDF reports) are reassembled and checked; counts are written to $SDQ_BRIDGE_STATS.
test_theory `path` arguments are sent as an uploaded Dify File (as a Dify chat attachment would be), and with --files-dir
run_script calls whose script contains $FILES get every file in DIR uploaded; files are served by a local HTTP server
(127.0.0.1 only), exercising the SDK's real file-download path.
"""
import base64, functools, http.server, json, os, shutil, subprocess, sys, tempfile, threading, zipfile
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LISTS = ("excerpts", "assumptions", "variables")


def log(*a):
    sys.stderr.write("[dify-bridge] " + " ".join(str(x) for x in a) + "\n"); sys.stderr.flush()


class Runtime(object):
    def __init__(self, cli, package):
        self.cwd = tempfile.mkdtemp(prefix="sdq-dify-run-")
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "TMPDIR", "UV_CACHE_DIR", "UV_INDEX_URL", "PIP_INDEX_URL", "SSL_CERT_FILE", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")}
        env["HOME"] = self.cwd
        self.p = subprocess.Popen([cli, "plugin", "run", os.path.abspath(package), "-r", "json"], cwd=self.cwd, env=env,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open(os.path.join(self.cwd, "daemon.log"), "wb"),
                                  start_new_session=True)
        self.n = 0
        for raw in self.p.stdout:
            msg = json.loads(raw)
            if msg.get("type") == "plugin_ready": break
            if msg.get("type") == "error": raise RuntimeError("plugin failed to start: %s" % msg.get("response"))
        else:
            raise RuntimeError("plugin runtime exited before plugin_ready; see " + os.path.join(self.cwd, "daemon.log"))
        log("plugin ready (real Dify local runtime)")

    def invoke(self, tool, params):
        self.n += 1; iid = "e2e-%d" % self.n
        req = {"invoke_id": iid, "type": "tool", "action": "invoke_tool",
               "request": {"type": "tool", "action": "invoke_tool", "user_id": "e2e", "provider": "spindoctor_qwerty",
                           "tool": tool, "credentials": {}, "tool_parameters": params}}
        self.p.stdin.write((json.dumps(req) + "\n").encode("utf-8")); self.p.stdin.flush()
        msgs = []
        for raw in self.p.stdout:
            m = json.loads(raw)
            if m.get("invoke_id") != iid: continue
            if m["type"] == "plugin_response": msgs.append(m["response"])
            elif m["type"] == "plugin_invoke_end": return msgs
            elif m["type"] == "error": raise RuntimeError(str(m["response"]))
        raise RuntimeError("plugin runtime closed the stream")

    def close(self):
        try:
            os.killpg(self.p.pid, 15); self.p.wait(15)
        except Exception:
            try: os.killpg(self.p.pid, 9)
            except Exception: pass


class Files(object):
    """Serves a private temp folder on 127.0.0.1 so uploads behave like Dify File objects (downloaded by the SDK)."""
    def __init__(self):
        self.folder = tempfile.mkdtemp(prefix="sdq-dify-files-"); self.n = 0
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a, **k): pass
        h = functools.partial(Quiet, directory=self.folder)
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def upload(self, path):
        self.n += 1; sub = os.path.join(self.folder, "u%04d" % self.n); os.makedirs(sub)
        n = os.path.basename(path); shutil.copy(path, os.path.join(sub, n))
        return {"dify_model_identity": "__dify__file__", "url": "http://127.0.0.1:%d/u%04d/%s" % (self.srv.server_port, self.n, quote(n)),
                "filename": n, "extension": os.path.splitext(n)[1], "mime_type": "application/octet-stream", "size": os.path.getsize(path), "type": "document"}

    def close(self):
        self.srv.shutdown(); shutil.rmtree(self.folder, ignore_errors=True)


def tool_list(package):
    import yaml  # noqa: F401  (PyYAML ships with the dify_plugin SDK; only needed by this harness)
    with zipfile.ZipFile(package) as z:
        prov = yaml.safe_load(z.read("provider/spindoctor_qwerty.yaml"))
        man = yaml.safe_load(z.read("manifest.yaml"))
        tools = []
        for t in prov["tools"]:
            d = yaml.safe_load(z.read(t))
            props = {p["name"]: {"type": "string", "description": p.get("llm_description") or p["human_description"]["en_US"]}
                     for p in d["parameters"] if p.get("form") == "llm"}
            tools.append({"name": d["identity"]["name"], "description": d["description"]["llm"],
                          "inputSchema": {"type": "object", "properties": props, "required": [p["name"] for p in d["parameters"] if p.get("required")]}})
    return man, tools


def seed_workspace(ws):
    ms, fs = os.environ.get("SPINDOCTOR_MEASUREMENT_SEED"), os.environ.get("SPINDOCTOR_FIELD_SEED")
    if not ws or not (ms or fs) or os.path.exists(os.path.join(ws, "spindoctor-cartridge-session.json")): return
    sys.path.insert(0, ROOT)
    from spindoctor.terminal import Session
    Session(ws, measurement_seed=ms, field_seed=fs).save()


def to_dify(name, args, files, files_dir):
    p = dict(args or {})
    if not p.get("workspace") and name not in ("spindoctor_functions", "spindoctor_list_presets") and os.environ.get("SPINDOCTOR_WORKSPACE"):
        p["workspace"] = os.environ["SPINDOCTOR_WORKSPACE"]
    for k in LISTS:
        if isinstance(p.get(k), list): p[k] = "\n".join(str(x) for x in p[k])
    if isinstance(p.get("checks"), (list, dict)): p["checks"] = json.dumps(p["checks"])
    if isinstance(p.get("overrides"), dict): p["overrides"] = " ".join("%s=%s" % kv for kv in p["overrides"].items())
    if name == "spindoctor_run_script" and files_dir and "$FILES" in str(p.get("script", "")):
        p["files"] = [files.upload(os.path.join(files_dir, n)) for n in sorted(os.listdir(files_dir)) if os.path.isfile(os.path.join(files_dir, n))]
    if name == "spindoctor_test_theory" and p.get("path") and os.path.isfile(p["path"]):
        p["file"] = files.upload(p.pop("path"))  # attachments reach a Dify plugin as uploaded files, never as host paths
    return p


def main():
    a = sys.argv[1:]
    opt = dict(zip(a[::2], a[1::2]))
    cli, package = opt["--cli"], opt["--package"]
    man, tools = tool_list(package)
    files, files_dir = Files(), opt.get("--files-dir")
    rt = Runtime(cli, package)
    stats = {"calls": 0, "blobs": 0, "pdfBlobs": 0, "txtBlobs": 0, "badBlobs": 0, "fileUploads": 0, "tools": sorted(t["name"] for t in tools)}
    try:
        for line in sys.stdin:
            if not line.strip(): continue
            req = json.loads(line); mid = req.get("id"); method = req.get("method")
            if mid is None: continue
            try:
                if method == "initialize":
                    res = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "spindoctor-qwerty-dify (dify plugin run)", "version": str(man["version"])}}
                elif method == "tools/list":
                    res = {"tools": tools}
                elif method == "tools/call":
                    name = req["params"]["name"]; params = to_dify(name, req["params"].get("arguments"), files, files_dir)
                    stats["fileUploads"] += len(params.get("files") or []) + (1 if params.get("file") else 0)
                    seed_workspace(params.get("workspace"))
                    msgs = rt.invoke(name, params); stats["calls"] += 1
                    text, obj, chunks = "", None, {}
                    for m in msgs:
                        t, body = m.get("type"), m.get("message") or {}
                        if t == "text": text += body.get("text", "")
                        elif t == "json": obj = body.get("json_object")
                        elif t == "blob_chunk":
                            c = chunks.setdefault(body["id"], {"parts": [], "meta": m.get("meta") or {}}); c["parts"].append(base64.b64decode(body.get("blob") or ""))
                        elif t == "blob":
                            chunks.setdefault(str(len(chunks)), {"parts": [base64.b64decode(body.get("blob") or "")], "meta": m.get("meta") or {}})
                    for c in chunks.values():
                        data = b"".join(c["parts"]); fn = str((c["meta"] or {}).get("filename", ""))
                        stats["blobs"] += 1
                        if fn.endswith(".pdf"):
                            stats["pdfBlobs"] += 1
                            if not (data.startswith(b"%PDF-1.") and b"%%EOF" in data[-1024:]): stats["badBlobs"] += 1
                        elif fn.endswith(".txt"):
                            stats["txtBlobs"] += 1
                            if not data: stats["badBlobs"] += 1
                    res = {"content": [{"type": "text", "text": text}], "structuredContent": obj or {}, "isError": not (obj or {}).get("ok", False)}
                else:
                    raise RuntimeError("unsupported method " + str(method))
                out = {"jsonrpc": "2.0", "id": mid, "result": res}
            except Exception as e:  # noqa: BLE001
                out = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32000, "message": str(e)}}
            sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()
    finally:
        rt.close(); files.close()
        if os.environ.get("SDQ_BRIDGE_STATS"):
            try:
                prev = json.load(open(os.environ["SDQ_BRIDGE_STATS"])) if os.path.exists(os.environ["SDQ_BRIDGE_STATS"]) else []
            except ValueError:
                prev = []
            json.dump(prev + [stats], open(os.environ["SDQ_BRIDGE_STATS"], "w"), indent=1)


if __name__ == "__main__":
    main()
