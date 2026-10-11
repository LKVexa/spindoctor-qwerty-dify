# SpinDoctor Qwerty for Dify 1.1.0 - shared glue between the Dify tools and the bundled engine
# Copyright (C) 2026 RUSSELL PHILIP SMITHSON <russellsmithson77@outlook.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. It is distributed WITHOUT ANY WARRANTY; see the LICENSE file for details.
"""Calls the bundled, standard-library-only SpinDoctor engine in-process and turns its result into Dify tool
messages: the function table / compact JSON as text, the full result as JSON, and (optionally) the newest TXT+PDF
report as file blobs so they can be opened in a Dify chat. No network access; nothing runs until a tool is called.

The Dify plugin daemon only passes an allow-list of environment variables (PATH, HOME, TMPDIR, ...) to plugins, so
SPINDOCTOR_* variables set on the daemon do NOT reach this code; use the tool's `workspace` setting instead."""
import json
import os
import shutil
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from spindoctor import api  # noqa: E402

VERSION = "1.1.0"
WORKSPACE = os.environ.get("SPINDOCTOR_WORKSPACE") or os.path.join(tempfile.gettempdir(), "spindoctor-workspace")
TEXT_LIMIT = 60000
MAX_BLOB = 10 * 1024 * 1024
MAX_UPLOADS = 128                     # q.folder accepts 1-128 supported files per job
MAX_UPLOAD_BYTES = 4 * 1024 * 1024    # and 4 MiB per file
_MIME = {".pdf": "application/pdf", ".txt": "text/plain", ".csv": "text/csv", ".json": "application/json"}
NO_WORKSPACE = {"spindoctor_list_presets", "spindoctor_functions"}


def _lines(v):
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    return [x for x in str(v).splitlines() if x.strip()]


def _safe_name(name, fallback):
    base = os.path.basename(str(name or "").replace("\\", "/")).strip().lstrip(".")
    return base[:200] or fallback


def _save_upload(f, folder, fallback):
    blob = f.blob  # Dify File: downloaded from the Dify file server (FILES_URL)
    if len(blob) > MAX_UPLOAD_BYTES:
        raise ValueError("Uploaded file %s is larger than 4 MiB." % (getattr(f, "filename", None) or fallback))
    path = os.path.join(folder, _safe_name(getattr(f, "filename", None), fallback))
    with open(path, "wb") as fh:
        fh.write(blob)
    return path


def prepare(name, params):
    """Dify parameters -> engine arguments. Returns (args, temp_dirs, error)."""
    args = {k: v for k, v in dict(params or {}).items() if v is not None and v != ""}
    attach = args.pop("attach_reports", True)
    temps = []
    try:
        if name == "spindoctor_run_script":
            files = args.pop("files", None) or []
            if files:
                if len(files) > MAX_UPLOADS:
                    raise ValueError("At most 128 files can be uploaded for one q.folder job.")
                d = tempfile.mkdtemp(prefix="sdq-files-"); temps.append(d)
                for i, f in enumerate(files):
                    _save_upload(f, d, "file%03d.txt" % i)
                args["script"] = str(args.get("script", "")).replace("$FILES", d.replace("\\", "/"))
            elif "$FILES" in str(args.get("script", "")):
                raise ValueError("The script uses $FILES but no files were uploaded.")
        elif name == "spindoctor_run_preset":
            ov = args.get("overrides")
            if isinstance(ov, str):
                pairs = [p for p in ov.replace(",", " ").split() if p]
                bad = [p for p in pairs if "=" not in p]
                if bad:
                    raise ValueError("Overrides must be name=value pairs, e.g. 'shots=4096 basis=x' (got %s)." % ", ".join(bad))
                args["overrides"] = dict(p.split("=", 1) for p in pairs)
        elif name == "spindoctor_report":
            if "limit" in args:
                args["limit"] = int(float(args["limit"]))
        elif name == "spindoctor_test_theory":
            f = args.pop("file", None)
            if f is not None:
                d = tempfile.mkdtemp(prefix="sdq-theory-"); temps.append(d)
                args["path"] = _save_upload(f, d, "theory.txt")
                if args.get("source") not in ("file", "chat"):
                    args["source"] = "file"
            for k in ("excerpts", "assumptions", "variables"):
                if k in args:
                    args[k] = _lines(args[k])
            if isinstance(args.get("checks"), str):
                try:
                    c = json.loads(args["checks"])
                except ValueError as e:
                    raise ValueError("checks must be a JSON array of check objects: %s" % e)
                args["checks"] = c if isinstance(c, list) else [c]
        if name not in NO_WORKSPACE:
            args.setdefault("workspace", WORKSPACE)
        else:
            args.pop("workspace", None)
        return args, temps, None, attach
    except Exception as e:  # noqa: BLE001
        for d in temps:
            shutil.rmtree(d, ignore_errors=True)
        return args, [], str(e), attach


def _report_paths(out):
    found = []
    def walk(o):
        if isinstance(o, dict):
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
        elif isinstance(o, str) and os.path.isabs(o) and o.lower().endswith((".pdf", ".txt")):
            found.append(o)
    walk(out)
    return found


def attachments(out):
    """Newest PDF report plus its TXT twin (or the newest TXT when no PDF exists)."""
    paths = [p for p in _report_paths(out) if os.path.isfile(p)]
    pdfs = [p for p in paths if p.lower().endswith(".pdf")]
    pick = []
    if pdfs:
        pick.append(pdfs[-1])
        twin = pdfs[-1][:-4] + ".txt"
        if os.path.isfile(twin):
            pick.insert(0, twin)
    elif paths:
        pick.append(paths[-1])
    return [p for p in pick if os.path.getsize(p) <= MAX_BLOB]


def call(name, args):
    try:
        out = api.call(name, args)
    except Exception as e:  # noqa: BLE001
        out = {"ok": False, "error": str(e)}
    if isinstance(out, dict):
        out.setdefault("cartridge", "SpinDoctor Qwerty %s for Dify" % VERSION)
    text = out["markdown"] if out.get("ok") and isinstance(out.get("markdown"), str) else api.as_json(out)
    return out, (text if len(text) <= TEXT_LIMIT else text[:TEXT_LIMIT] + "\n...[truncated; open the attached or listed report files for full output]")


def invoke(tool, name, params):
    args, temps, err, attach = prepare(name, params)
    try:
        if err:
            out = {"ok": False, "error": err, "guardrail": api.GUARDRAIL}
            text = api.as_json(out)
        else:
            out, text = call(name, args)
        yield tool.create_text_message(text)
        yield tool.create_json_message(out)
        if attach and not err and name not in NO_WORKSPACE:
            for p in attachments(out):
                with open(p, "rb") as fh:
                    data = fh.read()
                yield tool.create_blob_message(data, meta={"mime_type": _MIME.get(os.path.splitext(p)[1].lower(), "application/octet-stream"), "filename": os.path.basename(p)})
    finally:
        for d in temps:
            shutil.rmtree(d, ignore_errors=True)
