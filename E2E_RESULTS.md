# End-to-end results: spindoctor-qwerty-dify 1.1.0

Run on 2026-10-11 (PT) in a clean-room copy (the staged repo copied into an empty folder, empty HOME, no access to engine
development folders), following only this README: `python3 -m venv .venv`, `.venv/bin/pip install -r requirements.txt`
(dify_plugin 0.10.2 from PyPI), the official Dify plugin CLI 0.6.11 downloaded from the dify-plugin-daemon GitHub release,
`python3 scripts/build_difypkg.py --cli ./dify-plugin`, then `.venv/bin/python tests/dify_host_check.py --cli ./dify-plugin`.

**Mode: real Dify plugin runtime; Dify server host-simulated.** `dify plugin package` (official CLI) validated and packed the
plugin, and `dify plugin run` - the plugin daemon's own local runtime, which needs no Dify server, account, sign-in or API key -
unpacked the package, installed `requirements.txt` with uv, started `main.py` under the dify_plugin SDK and answered real
`invoke_tool` requests over its JSON stdio interface. A Dify server (web app, API, database, model provider) was not installed, so
`tests/dify_bridge.py` stands in for it: it sends the same tool requests Dify sends, serves uploaded files as Dify file objects from
127.0.0.1 (exercising the SDK's real download path) and reassembles the attached report blobs. The daemon passes only an
allow-listed environment to plugins (checked in its source, `internal/core/local_runtime/subprocess.go`), so the workspace is sent as
the tool's Workspace folder setting; for the reference comparison the bridge pre-seeds a new workspace once with the reference seeds.

**Format check:** Dify plugin docs (docs.dify.ai/en/develop-plugin, read 2026-10-11) and the CLI's own `plugin init` template
(0.6.11): manifest fields, `meta.version` 0.0.1, Python 3.12 runner, `.difyignore` (read instead of `.gitignore`), tool parameter
types (`select` with options, `file`, `files`, `boolean`, `number`) and forms (`llm`, `form`). Self-hosted Dify verifies signatures
by default: the README documents signing (tested with a throwaway key pair) and the `FORCE_VERIFYING_SIGNATURE=false` option.

**Parity target:** the updated SpinDoctor 3.1.2. Publishing was approved by Russell on the basis of the updated 3.1.2 passing its
own suite 18/18, with the three 29-qubit test checks adapted to the 298-qubit limit.

## README steps + host check (clean room)

```
built dist/spindoctor_qwerty-1.1.0.difypkg (official Dify CLI, 48 files, 234678 bytes)
sha256 8789cc3d2dd3615da4d1fa309481bc770cff7c845a3f6074e740168f086110f1
PASS manifest.yaml: required fields, version 1.1.0, type plugin, Python 3.12 runner, entrypoint main
PASS provider: 6 tools named exactly like the engine (function table matches), every engine parameter exposed
PASS GPL-3.0-or-later SPDX header in every .py/.yaml (43 files)
PASS requirements.txt pins the current dify_plugin SDK line (>=0.10.2,<0.11.0)
PASS glue: overrides/checks/excerpts conversion, clear errors for bad overrides, bad checks JSON, $FILES without uploads
PASS built-in packer is deterministic (two builds, identical bytes)
PASS official `dify plugin package` (CLI v0.6.11) validates and packs deterministically
PASS package: CLI and built-in packer hold identical files; no tests/scripts/examples/.git; engine + 6 tools inside (48 files)
PASS optional signing: build --sign (category community) then `dify signature verify` with the public key
PASS real Dify runtime (`dify plugin run`): shared E2E SUMMARY 12/12 (tools, function table, every family, 298q, q.folder, theory file/chat/transcript, presets vs 3.1.2 reference, PDFs)
    PASS initialize (server spindoctor-qwerty-dify (dify plugin run) 1.1.0)
    PASS tools/list exposes the 6 tools
    PASS function table (Markdown, 19 sections, 298-qubit limits listed)
    PASS 241 presets listed
    PASS one script per command family (16 families, every table example)
    PASS 298-qubit circuit with mcx7 (prepared-factor-Born-Z)
    PASS q.folder on mixed .txt/.csv/.json/.qasm folder (+ .md skipped)
    PASS theory from a file -> supported, TXT+PDF report
    PASS theory from a chat summary + quoted excerpts -> supported
    PASS theory from an exported chat transcript -> supported
    PASS presets qc-001..qc-025 match the updated 3.1.2 reference (20 identical, 5 documented differences)
    PASS TXT+PDF reports valid (255 PDFs, 255 TXT twins)
    SUMMARY 12/12 passed
PASS uploaded files -> $FILES -> q.folder run completes (2 command files, .md skipped)
PASS errors come back as ok=false with a clear message (unknown preset, bad checks JSON, report path escape)
PASS report files attached as Dify blobs (48 PDF + 48 TXT over 52 calls, 5 uploads), all valid
PASS no plugin runtime left running
HOST CHECK 14/14 passed
```

## Notes

- **Deterministic package:** the official CLI writes files sorted by path with no timestamps; two builds of the same sources give
  identical bytes. The built-in packer (`--builtin`) holds exactly the same files and contents (checked) with different zip bytes.
- **Preset differences (5 of qc-001..qc-025):** CPU-only reference instead of OpenCL GPU fields, tranche checkpoint text, state
  file name. They're documented in `tests/e2e_mcp.py` and are the same in every spindoctor-qwerty repo.
- **Not tested:** a full Dify server (installing through the Plugins page, signature enforcement, an agent or workflow choosing the
  tools, Dify's file server and chat rendering of the attached reports), Dify Cloud, the remote-debug mode, Windows and macOS.
