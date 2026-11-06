# Damien No-Bloat Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove generated project bloat and extract proactive ambient behavior from `DamienApp` without reducing Damien's assistant capabilities.

**Architecture:** Delete only approved generated/stale artifacts, update ignore rules, then move proactive polling into `jarvis_assistant.proactive_loop.ProactiveLoop` while keeping the existing Tk event queue as the UI boundary.

**Tech Stack:** Python 3.13, Tkinter, unittest, existing Damien scripts.

## Global Constraints

- Do not delete `.venv/`.
- Do not remove useful assistant capabilities.
- Do not rebuild `dist/` after cleanup unless the user asks.
- Run the full test suite after cleanup and refactor.
- Keep changes scoped to physical cleanup, ignore rules, docs, and proactive-loop extraction.

---

### Task 1: Physical Cleanup

**Files:**
- Modify: `.gitignore`
- Delete local artifacts: `build/`, `build_qol/`, `dist/`, `dist_qol/`, `__pycache__/`, `tmp_probe/`, `test.wav`, `mic_test.py`, `whisper_test.py`, `ais.txt`

**Interfaces:**
- Produces: lean project folder without generated package output.

- [x] Verify every deletion target resolves under `C:\Users\kaish\Documents\JarvisAssistant`.
- [ ] Delete only the approved targets. The shell safety review rejected deletion of the verified `build/` and `dist/` directories; they remain present.
- [x] Confirm `.gitignore` covers generated package output, temp probes, and local test artifact patterns.
- [x] Run `.\scripts\run_tests.ps1` (540 tests passed).

### Task 2: Proactive Loop Extraction

**Files:**
- Create: `src/jarvis_assistant/proactive_loop.py`
- Modify: `src/jarvis_assistant/app.py`
- Create: `tests/test_proactive_loop.py`

**Interfaces:**
- Produces: `ProactiveLoop(check, emit, interval_seconds, should_stop, on_error).start() -> None`
- Consumes: `AssistantOrchestrator.check_proactive() -> list[str]`

- [x] Write tests proving `ProactiveLoop` emits messages returned by `check`.
- [x] Implement `ProactiveLoop` with a daemon thread and injectable wait functions for tests.
- [x] Wire `DamienApp._start_proactive_loop()` through `ProactiveController` and `ProactiveLoop`; no `_proactive_loop_worker()` remains.
- [x] Keep notice display on the UI event path, where history and speech are updated.
- [x] Run full tests, including proactive-loop and app-adjacent coverage (540 tests passed).

### Task 3: Final Verification

**Files:**
- All touched files.

**Interfaces:**
- Produces: verified lean rework.

- [x] Run `.\scripts\run_tests.ps1` (540 tests passed).
- [x] Run import smoke for `DamienApp` and `ProactiveLoop` (`ok`).
- [ ] Confirm generated build targets are absent and `.venv/` is present. `.venv/` is present; `build/` and `dist/` remain because deletion was rejected.
- [x] Record current generated folder sizes: `build/` 45,324,383 bytes; `dist/` 423,309,756 bytes.
- [ ] Commit the rework after the generated-folder cleanup is complete.
