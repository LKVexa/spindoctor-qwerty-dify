# Changelog

## 1.1.0 - 2026-10-11

- Engine 1.1.0 at parity with the updated SpinDoctor 3.1.2: 1-298 logical qubits (59 per entangled factor), the `mcx7` gate,
  wide-register Born-Z sampling, `q.folder` with 3.1.2 semantics (.qasm2/.circuit, skipped-file listing, compact status, 128 files /
  4 MiB / 128 commands / 4096 characters), CSV report copies and measurement-CSV fitting equations. All 241 presets replayed.
- Tools renamed to the engine names (`spindoctor_run_script`, ...) so the in-chat function table matches what Dify shows.
- Reports are now attached to the answer as files (newest TXT + PDF, max 10 MB each; setting *Attach reports*). 1.0 returned only
  paths on the plugin host, which a Dify user can't open.
- `q.folder` from Dify: new `files` upload parameter and `$FILES` placeholder (1.0 could only name folders on the plugin host).
- New *Workspace folder* setting on every tool. The Dify daemon passes only an allow-list of environment variables to plugins, so the
  `SPINDOCTOR_WORKSPACE` variable 1.0 relied on never reached the plugin.
- `spindoctor_test_theory` now exposes every engine parameter (assumptions, variables, isolate); `action`, `source` and `section` are
  select lists; uploads are saved under a sanitised name, limited to 4 MiB and deleted after the call; bad `checks` JSON or bad
  overrides give a clear error instead of a traceback.
- `dify_plugin` requirement moved from `>=0.4.0,<0.8.0` to the current `>=0.10.2,<0.11.0`; manifest gains `tags`, `repo`,
  `verified: false` and a fixed `created_at`; descriptions updated from SpinDoctor 3.0.3 to 3.1.2.
- New deterministic build script (`scripts/build_difypkg.py`: official CLI or built-in packer, optional `--sign`), and a host check
  that runs the plugin in the official Dify plugin runtime (`dify plugin run`).
- Repository layout: the repo root is the plugin project (1.0 shipped a `spindoctor_qwerty/` folder plus a prebuilt package).
- License changed from MIT to GPL-3.0-or-later. Author RUSSELL PHILIP SMITHSON. README, NOTICE, COPYRIGHT and SPDX headers added.

## 1.0.0

- First release: `spindoctor_qwerty/` plugin project and a prebuilt `spindoctor_qwerty.difypkg` (tools run_script, run_preset,
  list_presets, report, functions, test_theory).
