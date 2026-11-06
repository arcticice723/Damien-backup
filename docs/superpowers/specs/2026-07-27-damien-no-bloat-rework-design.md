# Damien No-Bloat Rework Design

## Purpose

Damien should stay capable while becoming leaner to work on, easier to package, and less cluttered on disk. "No bloat" means removing generated physical weight and reducing architecture concentration without deleting useful assistant capabilities.

## Scope

This rework has two deliverables:

1. Physical cleanup: remove generated build/package output, cache folders, temp probes, and stale ad-hoc test artifacts from the project folder.
2. Architecture cleanup: move non-UI runtime responsibilities out of the giant desktop app class into focused modules, starting with proactive ambient behavior.

The virtual environment stays. `.venv/` is large, but it is the development environment and should not be deleted unless the user explicitly asks.

## Physical Cleanup

Remove these generated or stale local artifacts:

- `build/`
- `build_qol/`
- `dist/`
- `dist_qol/`
- `__pycache__/`
- `tmp_probe/`
- `test.wav`
- `mic_test.py`
- `whisper_test.py`
- `ais.txt`

Keep these:

- `.venv/`
- `assets/`
- `config/`
- `approved_documents/`
- `history/`, `logs/`, and `memory/` as local runtime data, but ensure they remain ignored.

Update `.gitignore` so generated package output and local runtime artifacts do not come back accidentally.

## Architecture Cleanup

`src/jarvis_assistant/app.py` currently owns too many responsibilities: UI construction, event handling, voice/wake control, streaming response handling, settings, diagnostics, provider checks, remote input, mascot behavior, and proactive reminders.

The first architecture slimming step is to extract proactive ambient behavior from `DamienApp` into a focused module:

- Create `src/jarvis_assistant/proactive_loop.py`.
- Move background proactive polling and notice display coordination out of `app.py`.
- Keep UI mutation inside the Tk thread by emitting events through the existing queue.
- Keep `AssistantOrchestrator.check_proactive()` as the source of proactive messages.

This split proves the pattern for later extractions without a risky all-at-once UI rewrite.

## Not In This Slice

Do not remove useful assistant abilities.

Do not split all of `app.py` at once.

Do not delete `.venv/`.

Do not rebuild `dist/` after cleanup unless the user asks.

## Verification

Before completion:

- Confirm generated folders and stale artifacts are gone.
- Confirm `.venv/` remains.
- Run full tests with `.\scripts\run_tests.ps1`.
- Run an import smoke test for `DamienApp` and the extracted proactive loop.
- Review the final file sizes for the largest project folders.
