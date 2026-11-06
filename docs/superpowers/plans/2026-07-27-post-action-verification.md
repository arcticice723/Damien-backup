# Post-Action Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Damien verifies action outcomes like Discord calls and game lobby entry by repeatedly reading visible app state and capturing screen evidence when confirmation fails.

**Architecture:** Add a reusable post-action verifier around existing `TaskStatusMonitor`, `visible_window_contains`, and `ScreenReader`. Discord and lobby automation will use this verifier so status checks are consistent and failures include screen evidence for self-improvement.

**Tech Stack:** Python 3, unittest, pywinauto UI Automation when available, Pillow screen capture through the existing `ScreenReader`.

## Global Constraints

- Keep destructive actions blocked unless the user explicitly approves them.
- Use existing low-risk tool routing and self-improvement queue patterns.
- Screen access must respect `screen_access_enabled`.
- Tests must use fakes/mocks for UI Automation and screenshots.

---

### Task 1: Reusable Verification Result

**Files:**
- Modify: `src/jarvis_assistant/task_status.py`
- Test: `tests/test_task_status.py`

**Interfaces:**
- Produces: `VisibleStatusVerifier(root: Path, max_checks: int = 8, interval_seconds: float = 1.0)`
- Produces: `VisibleStatusVerifier.verify(title_pattern: str, phrases: tuple[str, ...]) -> TaskStatus`

- [x] Write failing tests proving failed verification captures screen evidence and successful verification does not.
- [x] Run focused task status tests and verify failure.
- [x] Implement `VisibleStatusVerifier` with `TaskStatusMonitor`, `visible_window_contains`, and `ScreenReader.capture_screen`.
- [x] Run focused task status tests and verify pass.

### Task 2: Discord Verification Uses Screen Evidence

**Files:**
- Modify: `src/jarvis_assistant/discord_control.py`
- Test: `tests/test_discord_control.py`

**Interfaces:**
- Consumes: `VisibleStatusVerifier.verify(...) -> TaskStatus`

- [x] Write a failing test proving Discord call failure includes captured screen evidence in the queued reason.
- [x] Run focused Discord tests and verify failure.
- [x] Replace direct `TaskStatusMonitor` usage with `VisibleStatusVerifier`.
- [x] Run focused Discord tests and verify pass.

### Task 3: Lobby Verification Uses Screen Evidence

**Files:**
- Modify: `src/jarvis_assistant/game_lobby.py`
- Test: `tests/test_game_lobby.py`

**Interfaces:**
- Consumes: `VisibleStatusVerifier.verify(...) -> TaskStatus`

- [x] Write a failing test proving lobby failure includes captured screen evidence in the queued reason.
- [x] Run focused lobby tests and verify failure.
- [x] Replace direct lobby status polling with `VisibleStatusVerifier`.
- [x] Update app-open copy to say Damien is monitoring lobby status, not that it is already there.
- [x] Run focused lobby and command tests and verify pass.

### Task 4: Verification Pass

**Files:**
- Test: full suite

- [x] Run focused suites: task status, Discord, lobby, commands, orchestrator.
- [x] Run full unittest discovery in `.venv`.
- [x] Review the diff for bugs, errors, and scope creep.
