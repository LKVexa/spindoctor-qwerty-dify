# SpinDoctor Qwerty for Dify

**Dify tool plugin for the SpinDoctor 3.1.2 quantum-circuit simulator.** It adds a tool provider with six tools to
[Dify](https://dify.ai) (self-hosted or cloud) for use in agents, chatflows and workflows: build and run `q.*` circuits
(1-298 logical qubits), run the 241 built-in presets, run uploaded folders of command files with `q.folder`, test theories
from an uploaded file, pasted text or the conversation itself, and get TXT, PDF, JSON and CSV reports. The newest TXT and PDF
report are attached to each answer as files, so you can open them right in the Dify chat. Everything runs inside the Dify
plugin runtime in a bundled, standard-library-only Python engine. No credentials, no network calls.

> **Honest limits:** SpinDoctor is a **classical** FP64 simulator running on the Dify plugin host. It is not a quantum computer,
> does not connect to quantum hardware and gives no quantum speed-up or advantage. Registers hold 1-298 logical qubits, but one
> entangled group (factor) is limited to 59 qubits and dense factors to the memory budget (2^n x 16 bytes, and this plugin asks
> Dify for 1 GiB); registers wider than 29 qubits sample in basis Z only. Histograms come from seeded Born sampling. The engine
> needs **Python 3.8+**; Dify runs plugins on Python 3.12.

Version **1.1.0** (engine 1.1.0, "SpinDoctor 3.1.2 parity"). Author: RUSSELL PHILIP SMITHSON. License: GPL-3.0-or-later.

## What's in the plugin

The repo root is the plugin project (what `dify plugin package` packs). `.difyignore` keeps `tests/`, `scripts/`, `examples/` and
build output out of the package.

| Part | File | What it does |
|---|---|---|
| Manifest | `manifest.yaml` | `russellsmithson/spindoctor_qwerty` 1.1.0, Python 3.12 runner, 1 GiB memory, 100 MB plugin storage, tags, privacy, repo |
| Provider | `provider/spindoctor_qwerty.yaml` + `.py` | The tool provider (no credentials to configure) |
| Tools | `tools/spindoctor_*.yaml` + `.py` | `spindoctor_run_script`, `spindoctor_run_preset`, `spindoctor_list_presets`, `spindoctor_report`, `spindoctor_functions`, `spindoctor_test_theory` |
| Glue | `tools/_engine.py` | Converts Dify parameters, saves uploads to a temp folder, returns text + JSON + report files |
| Engine | `spindoctor/` | The SpinDoctor Qwerty engine 1.1.0 (standard library only) |
| Entry point | `main.py` | `dify_plugin` runner with a 600 s request timeout |
| Build | `scripts/build_difypkg.py` | Deterministic `.difypkg` build (official CLI or a built-in packer), optional signing |

Tool names match the engine and the function table exactly. Each tool also has two **settings** you fill in in Dify (the model
never sets them): **Workspace folder** (where state and reports live on the plugin host; default `<system temp>/spindoctor-workspace`)
and **Attach reports** (on by default). The Dify plugin daemon passes only a short allow-list of environment variables to plugins,
so `SPINDOCTOR_WORKSPACE` set on the daemon does not reach the plugin: use the Workspace folder setting instead.

## Build the .difypkg

The package is a binary file, so it isn't committed. Build it from a checkout; the same sources always give the same bytes.

```sh
git clone https://github.com/LKVexa/spindoctor-qwerty-dify
cd spindoctor-qwerty-dify
# official Dify plugin CLI (Linux x64 shown; pick your OS/arch from the release page)
curl -fL -o dify-plugin https://github.com/langgenius/dify-plugin-daemon/releases/download/0.6.11/dify-plugin-linux-amd64
chmod +x dify-plugin
python3 scripts/build_difypkg.py --cli ./dify-plugin
```

This writes `dist/spindoctor_qwerty-1.1.0.difypkg` and prints its SHA-256. Without the CLI, `python3 scripts/build_difypkg.py --builtin`
packs the same files with the standard library (identical contents, different zip bytes, no manifest validation). On Windows use
`python` and `dify-plugin-windows-amd64.exe`; on macOS `dify-plugin-darwin-arm64` or `-amd64` (or `brew install dify`).

## Install in Dify

1. In Dify open **Plugins -> Install plugin -> Local Package File** (or drag the `.difypkg` onto the Plugins page) and confirm.
2. **Self-hosted Dify checks plugin signatures by default** and rejects unsigned local packages. Either
   - **sign it (recommended):** `./dify-plugin signature generate -f mykey`, then
     `python3 scripts/build_difypkg.py --cli ./dify-plugin --sign mykey.private.pem`, and give the plugin daemon the public key
     (`THIRD_PARTY_SIGNATURE_VERIFICATION_ENABLED=true`, `THIRD_PARTY_SIGNATURE_VERIFICATION_PUBLIC_KEYS=<path in the container>`);
     install `dist/spindoctor_qwerty-1.1.0.signed.difypkg`; or
   - **for a test instance you control:** set `FORCE_VERIFYING_SIGNATURE=false` in `docker/.env` and restart
     (`docker compose down && docker compose up -d`).
   See Dify's [signature guide](https://docs.dify.ai/en/develop-plugin/publishing/standards/third-party-signature-verification)
   and [FAQ](https://docs.dify.ai/en/develop-plugin/publishing/faq/faq). Dify Cloud accepts only Marketplace plugins.
3. Dify installs the plugin's single dependency (`dify_plugin`) when it installs the package; that is the only download.
4. Add **SpinDoctor Qwerty** tools to an Agent or a workflow Tool node. There is nothing to authorize. Ask *"show the SpinDoctor
   functions"* to see the table below.

**Remote debugging** (developing against a Dify instance): copy the key from **Plugins -> Develop** into a `.env` file with
`INSTALL_METHOD=remote`, `REMOTE_INSTALL_URL=<host:port>` and `REMOTE_INSTALL_KEY=<key>`, then `pip install -r requirements.txt` and
`python -m main`. Never commit that `.env` file.

## SpinDoctor Qwerty - plugin tools

| Function | What it does | Command to type |
|---|---|---|
| Function table (spindoctor_functions) | Show this table in chat | Ask: "show the SpinDoctor functions" |
| Run a script (spindoctor_run_script) | Run any q.* lines above; returns results + TXT/JSON/CSV/PDF report paths | Ask: "run q.circuit new bell 2 / q.circuit add h 0 / ..." |
| Run a preset (spindoctor_run_preset) | Run qc-001..qc-241 with overrides | Ask: "run preset qc-067 with shots=64" |
| List presets (spindoctor_list_presets) | Search the 241 presets | Ask: "list presets about Grover" |
| Read a report (spindoctor_report) | List/read TXT reports (PDF/JSON paths alongside) | Ask: "show the newest SpinDoctor report" |
| Test a theory from a file (spindoctor_test_theory source=file) | Read a .txt/.md/.pdf/.py/.json/.csv/.q attachment, then hypothesis -> prediction -> q.* script -> run -> verdict + TXT/PDF theory report | Ask: "test the theory in C:/notes/theory.md" (the host must pass the file path/content) |
| Test a theory from text (spindoctor_test_theory source=text) | Same pipeline for pasted text | Ask: "test this theory: a Hadamard on \|0> gives 50/50" |
| Test the theory we discussed (spindoctor_test_theory source=chat) | The AI summarises the theory from the conversation (claims, assumptions, variables, prediction), you confirm, then it is tested; quoted excerpts go in the report under 'Source: chat history'. An exported chat transcript (.txt/.md/.json/.html) also works | Ask: "test the theory we discussed" or "test the theory in my exported chat C:/chats/conversation.json" |

Every command family is listed with a runnable example in **[FUNCTIONS.md](FUNCTIONS.md)** (the exact table the tool shows):
circuits (`q.circuit`, including 298-qubit wide registers and the `mcx7` gate), queries (`q.query`), the tranche register
(`q.tranche`), the procedural grid, presets and sequences, resource planning, math calculators, physics models, lessons, noise, error
correction, compilation, algorithms, inputs/folders/history (`q.input`, `q.folder`, `q.history`) and the cartridge commands.

## Theory testing

`spindoctor_test_theory` turns a claim into a test: hypothesis -> measurable prediction -> `q.*` script -> run -> compare -> a TXT +
JSON + PDF **theory test report** with the hypothesis, script, raw results, verdict (*supported*, *not supported* or *inconclusive*)
and limits. The report files are attached to the answer.

- **From a file:** attach a .txt, .md, .pdf, .py, .json, .csv or .q file to the `file` parameter (in a chat, upload it and let the
  agent pass it; in a workflow, wire a file variable). The plugin downloads it from Dify, reads it and deletes the copy afterwards.
- **From pasted text.**
- **From the chat history:** say *"test the theory we discussed"*. The model writes a short summary (claims, assumptions, variables,
  measurable prediction), shows it to you to confirm or correct, then passes it with optional quoted excerpts (one per line); the
  report records them under *Source: chat history*. Exported chat transcripts (.txt/.md/.json/.html from ChatGPT, Claude and others)
  can be attached as the file too.
- The plugin cannot read your conversation by itself: only the model sees it, and Dify's memory window or the model's context may
  already have dropped the start of a long conversation.

Sample theory files and chat transcripts are in `examples/theory/` (not part of the package).

## Folder ingestion (`q.folder`)

`q.folder run path="<folder>"` runs every supported file at the top level of a folder (.txt, .csv, .json, .qasm, .qasm2, .circuit,
.pdf) in ordinal name order: 1-128 supported files, at most 4 MiB per file, 1-128 commands per file and 4096 characters per command,
strict UTF-8. Other files (for example .md) are skipped and listed. The first failing file stops the job.

In Dify the plugin can't see your computer's folders, so upload the files to `spindoctor_run_script`'s `files` parameter and write
`q.folder run path="$FILES"`: the plugin saves the uploads into one fresh folder, puts its path in place of `$FILES`, runs the job and
deletes the folder afterwards. (A `path` on the plugin host itself also works, for example a folder mounted into the plugin daemon.)

## Testing

| Test | Command | Result for 1.1.0 |
|---|---|---|
| Host check (static + official Dify CLI + real plugin runtime) | `.venv/bin/python tests/dify_host_check.py --cli ./dify-plugin` | 14/14 checks, end-to-end 12/12 |

Set up once: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (the `dify_plugin` SDK and its dependencies) and the
CLI download from *Build the .difypkg*. On Windows use `.venv\Scripts\python`.

**Real plugin runtime, Dify server host-simulated.** The official Dify plugin CLI 0.6.11 (from the dify-plugin-daemon releases) packed
the plugin and ran it with `dify plugin run`, the daemon's own local runtime: it unpacked the package, installed `requirements.txt`
with uv (dify_plugin 0.10.2), started `main.py` under the SDK and answered real `invoke_tool` requests. No sign-in, API key or Dify
account was used. A Dify server (web app, API, database and model) was not installed, so `tests/dify_bridge.py` stands in for it: it
sends the same tool requests Dify sends, serves uploads as Dify file objects from 127.0.0.1 and reassembles the attached report files.
Whether a Dify agent picks the tools as intended isn't tested. Details in [E2E_RESULTS.md](E2E_RESULTS.md).

## Author and license

Author: **RUSSELL PHILIP SMITHSON** <russellsmithson77@outlook.com>

Copyright (C) 2026 RUSSELL PHILIP SMITHSON. Licensed under the GNU General Public License v3.0 or later (`GPL-3.0-or-later`): see
[LICENSE](LICENSE), [NOTICE](NOTICE) and [COPYRIGHT](COPYRIGHT). Dify's manifest has no license field; the license, NOTICE and
COPYRIGHT ship inside the package. The manifest `author` is the Dify plugin namespace `russellsmithson` (Dify allows only lowercase
letters, digits, `-` and `_`). Dify is a trademark of LangGenius, Inc.; this project is not affiliated with LangGenius.
