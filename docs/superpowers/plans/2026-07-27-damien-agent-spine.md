# Damien Agent Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Damien's first real agent spine with first-class notes, reminders, proactive triggers, and compatibility with the existing command tools.

**Architecture:** Add focused agent modules under `src/jarvis_assistant/agent/` and keep `AssistantOrchestrator.prepare()` as the app-facing entry point. The new runtime collects bounded context, plans notes/reminders/tool actions, executes through the existing `ToolRegistry`, verifies local stores, and returns the existing `OrchestrationResult` shape.

**Tech Stack:** Python 3.13, dataclasses, JSONL local stores, unittest, existing Tk app, existing Ollama/provider abstractions.

## Global Constraints

- Damien remains voice-first; responses should stay short and natural for speech.
- Damien remains free-first; paid providers are disabled unless explicitly approved later.
- The first implementation runs on the current PC and keeps the provider URL configurable for future LAN/server use.
- Tool execution stays on the user's device behind the existing risk policy.
- Dangerous actions remain denied and important actions remain confirmation-gated.
- Notes and reminders are local, inspectable, and do not save raw microphone audio.
- Server deployment, phone companion, calendar/email, full autonomous web agent, full project management, and paid provider integration are extension points, not first-slice implementation.

---

### Task 1: Agent Data Model And Context

**Files:**
- Create: `src/jarvis_assistant/agent/__init__.py`
- Create: `src/jarvis_assistant/agent/runtime.py`
- Create: `tests/test_agent_runtime.py`

**Interfaces:**
- Produces: `AgentContext`, `AgentPlan`, `AgentRuntime`, `AgentPlanKind`
- Consumes later: `AgentRuntime.prepare(text: str, base_messages: list[ChatMessage]) -> OrchestrationResult`

- [ ] **Step 1: Write failing tests for direct answer and tool compatibility**

```python
def test_agent_runtime_routes_existing_tool_fast_path():
    runtime = build_runtime_with_tool("what time is it", "Local time: Monday at 10:00 AM")
    result = runtime.prepare("what time is it", [ChatMessage("user", "what time is it")])
    assert result.direct_response == "Local time: Monday at 10:00 AM"
    assert [tool.name for tool in result.tool_results] == ["local_time"]

def test_agent_runtime_keeps_plain_conversation_for_model():
    runtime = build_runtime_without_tool()
    result = runtime.prepare("tell me a quick joke", [ChatMessage("user", "tell me a quick joke")])
    assert result.direct_response is None
    assert result.messages[-1] == ChatMessage("user", "tell me a quick joke")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='.\src'; .\.venv\Scripts\python.exe -m unittest tests.test_agent_runtime -v`
Expected: FAIL because `jarvis_assistant.agent.runtime` does not exist.

- [ ] **Step 3: Implement minimal agent runtime shell**

Create dataclasses for context and plans, then implement `AgentRuntime.prepare()` with the existing fast tool path and model fallback. The runtime should accept the same collaborators currently passed to `AssistantOrchestrator`: router, tools, audit, interpreter, improvement queue, and persona style.

- [ ] **Step 4: Run tests**

Run: `$env:PYTHONPATH='.\src'; .\.venv\Scripts\python.exe -m unittest tests.test_agent_runtime -v`
Expected: PASS.

### Task 2: Notes Store

**Files:**
- Create: `src/jarvis_assistant/agent/notes.py`
- Modify: `src/jarvis_assistant/agent/runtime.py`
- Test: `tests/test_agent_notes.py`

**Interfaces:**
- Produces: `NoteStore.add(content: str) -> NoteRecord`, `NoteStore.list_recent(limit: int = 10) -> list[NoteRecord]`, `NoteStore.search(query: str, limit: int = 10) -> list[NoteRecord]`
- Consumes: `AgentRuntime` uses `NoteStore` for `save_note`, note listing, and note search before falling back to model.

- [ ] **Step 1: Write failing note tests**

```python
def test_note_store_add_list_and_search(tmp_path):
    store = NoteStore(tmp_path / "notes.jsonl")
    store.add("call the dentist")
    store.add("buy milk")
    assert [note.content for note in store.list_recent()] == ["call the dentist", "buy milk"]
    assert [note.content for note in store.search("dentist")] == ["call the dentist"]

def test_agent_runtime_handles_natural_note_commands(tmp_path):
    runtime = build_runtime(root=tmp_path)
    save = runtime.prepare("remember as a note that the blue cable is for the monitor", [ChatMessage("user", "remember as a note that the blue cable is for the monitor")])
    listed = runtime.prepare("show my notes", [ChatMessage("user", "show my notes")])
    assert "Saved note" in save.direct_response
    assert "blue cable" in listed.direct_response
```

- [ ] **Step 2: Run tests to verify failure**

Run: `$env:PYTHONPATH='.\src'; .\.venv\Scripts\python.exe -m unittest tests.test_agent_notes -v`
Expected: FAIL because `NoteStore` does not exist.

- [ ] **Step 3: Implement note store and planner hooks**

Persist JSONL records with `id`, `created_at`, `content`, and `source`. Add regex hooks in the agent planner for natural note save/list/search commands. Keep existing `ToolRegistry` note commands compatible.

- [ ] **Step 4: Run note tests and tool tests**

Run: `$env:PYTHONPATH='.\src'; .\.venv\Scripts\python.exe -m unittest tests.test_agent_notes tests.test_tools -v`
Expected: PASS.

### Task 3: Reminder Store And Parser

**Files:**
- Create: `src/jarvis_assistant/agent/reminders.py`
- Modify: `src/jarvis_assistant/agent/runtime.py`
- Test: `tests/test_agent_reminders.py`

**Interfaces:**
- Produces: `ReminderStore.create(message: str, due_at: datetime) -> ReminderRecord`, `ReminderStore.pending(now: datetime) -> list[ReminderRecord]`, `ReminderStore.due(now: datetime) -> list[ReminderRecord]`, `ReminderStore.complete(reminder_id: str) -> ReminderRecord | None`
- Produces: `parse_reminder(text: str, now: datetime) -> ParsedReminder | None`
- Consumes: `AgentRuntime` handles create/list/complete reminder commands.

- [ ] **Step 1: Write failing reminder tests**

```python
def test_parse_relative_reminder():
    now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
    parsed = parse_reminder("remind me in 20 minutes to check the oven", now)
    assert parsed.message == "check the oven"
    assert parsed.due_at == now + timedelta(minutes=20)

def test_agent_runtime_creates_lists_and_completes_reminder(tmp_path):
    now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
    runtime = build_runtime(root=tmp_path, now=lambda: now)
    created = runtime.prepare("remind me in 20 minutes to stretch", [ChatMessage("user", "remind me in 20 minutes to stretch")])
    listed = runtime.prepare("list reminders", [ChatMessage("user", "list reminders")])
    completed = runtime.prepare("complete reminder 1", [ChatMessage("user", "complete reminder 1")])
    assert "Reminder set" in created.direct_response
    assert "stretch" in listed.direct_response
    assert "Completed reminder" in completed.direct_response
```

- [ ] **Step 2: Run tests to verify failure**

Run: `$env:PYTHONPATH='.\src'; .\.venv\Scripts\python.exe -m unittest tests.test_agent_reminders -v`
Expected: FAIL because reminders module does not exist.

- [ ] **Step 3: Implement reminder parsing and persistence**

Support "in N minutes/hours", "tomorrow at H[:MM] [AM/PM]", and "at H[:MM] [AM/PM]" for today or tomorrow when today's time has passed. If parsing fails for a reminder-like command, return a follow-up asking for the time.

- [ ] **Step 4: Run reminder tests**

Run: `$env:PYTHONPATH='.\src'; .\.venv\Scripts\python.exe -m unittest tests.test_agent_reminders -v`
Expected: PASS.

### Task 4: Proactive Engine

**Files:**
- Create: `src/jarvis_assistant/agent/proactive.py`
- Modify: `src/jarvis_assistant/agent/runtime.py`
- Test: `tests/test_agent_proactive.py`

**Interfaces:**
- Produces: `ProactiveEngine.check(now: datetime) -> list[ProactiveNotice]`
- Produces: `ProactiveEngine.dismiss(notice_id: str) -> None`
- Consumes: `ReminderStore`, failed action log path, and simple action history.

- [ ] **Step 1: Write failing proactive tests**

```python
def test_proactive_engine_surfaces_due_reminder_once(tmp_path):
    now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
    reminders = ReminderStore(tmp_path / "reminders.jsonl")
    reminders.create("stretch", now)
    engine = ProactiveEngine(reminders=reminders, state_path=tmp_path / "proactive.json")
    first = engine.check(now)
    second = engine.check(now)
    assert [notice.message for notice in first] == ["Reminder: stretch"]
    assert second == []

def test_agent_runtime_can_dismiss_proactive_suggestions(tmp_path):
    runtime = build_runtime(root=tmp_path)
    result = runtime.prepare("be quiet for an hour", [ChatMessage("user", "be quiet for an hour")])
    assert "quiet for an hour" in result.direct_response.lower()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `$env:PYTHONPATH='.\src'; .\.venv\Scripts\python.exe -m unittest tests.test_agent_proactive -v`
Expected: FAIL because proactive module does not exist.

- [ ] **Step 3: Implement proactive notices**

Implement due reminder notices, quiet-until state, dismissal IDs, and a hook for failed actions. Keep fullscreen/media guardrails as future-check hooks returning "allowed" by default because reliable detection is not in this first slice.

- [ ] **Step 4: Run proactive tests**

Run: `$env:PYTHONPATH='.\src'; .\.venv\Scripts\python.exe -m unittest tests.test_agent_proactive -v`
Expected: PASS.

### Task 5: Orchestrator Integration

**Files:**
- Modify: `src/jarvis_assistant/orchestrator.py`
- Modify: `src/jarvis_assistant/app.py`
- Modify: `src/jarvis_assistant/config.py`
- Test: `tests/test_orchestrator.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `AgentRuntime.prepare()`
- Produces: Existing `AssistantOrchestrator.prepare()` remains stable for app, remote, wake phrase, and tests.

- [ ] **Step 1: Write failing integration tests**

```python
def test_orchestrator_handles_reminder_through_agent_runtime():
    orchestrator = build_orchestrator(tmp_path)
    result = orchestrator.prepare("remind me in 10 minutes to drink water", [ChatMessage("user", "remind me in 10 minutes to drink water")])
    assert "Reminder set" in result.direct_response

def test_default_settings_include_proactive_controls(tmp_path):
    settings = load_settings(tmp_path / "settings.json")
    assert settings.proactive_enabled is True
    assert settings.reminder_check_seconds == 30
```

- [ ] **Step 2: Run integration tests to verify failure**

Run: `$env:PYTHONPATH='.\src'; .\.venv\Scripts\python.exe -m unittest tests.test_orchestrator tests.test_config -v`
Expected: FAIL on missing reminder handling and settings fields.

- [ ] **Step 3: Wire runtime into orchestrator**

Instantiate `AgentRuntime` inside `AssistantOrchestrator` with default note/reminder/proactive paths under `APP_ROOT`. Keep existing `OrchestrationResult` and `log_final()` unchanged. Add settings fields `proactive_enabled`, `proactive_voice_enabled`, and `reminder_check_seconds` with defaults.

- [ ] **Step 4: Run integration tests**

Run: `$env:PYTHONPATH='.\src'; .\.venv\Scripts\python.exe -m unittest tests.test_orchestrator tests.test_config -v`
Expected: PASS.

### Task 6: App Ambient Loop Hook

**Files:**
- Modify: `src/jarvis_assistant/app.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `AssistantOrchestrator.check_proactive() -> list[str]`
- Produces: Tk event queue entries that append and speak proactive notices.

- [ ] **Step 1: Write failing test for proactive check API**

```python
def test_orchestrator_check_proactive_returns_due_reminder_once():
    orchestrator = build_orchestrator_with_due_reminder(tmp_path)
    first = orchestrator.check_proactive()
    second = orchestrator.check_proactive()
    assert first == ["Reminder: stretch"]
    assert second == []
```

- [ ] **Step 2: Run test to verify failure**

Run: `$env:PYTHONPATH='.\src'; .\.venv\Scripts\python.exe -m unittest tests.test_orchestrator.AssistantOrchestratorTests.test_check_proactive_returns_due_reminder_once -v`
Expected: FAIL because `check_proactive()` does not exist.

- [ ] **Step 3: Implement app polling hook**

Add `AssistantOrchestrator.check_proactive()` and a DamienApp background thread that sleeps `settings.reminder_check_seconds`, calls the orchestrator, and queues proactive messages for the existing UI/speech event flow. In tests, cover the orchestrator API and keep app thread behavior minimal.

- [ ] **Step 4: Run focused tests**

Run: `$env:PYTHONPATH='.\src'; .\.venv\Scripts\python.exe -m unittest tests.test_orchestrator -v`
Expected: PASS.

### Task 7: Final Verification

**Files:**
- Modify docs only if behavior differs from the design.

**Interfaces:**
- Consumes all implemented modules.
- Produces verified working rework.

- [ ] **Step 1: Run full tests**

Run: `.\scripts\run_tests.ps1`
Expected: PASS.

- [ ] **Step 2: Run import smoke test**

Run: `python -c "from jarvis_assistant.orchestrator import AssistantOrchestrator; from jarvis_assistant.agent import AgentRuntime; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Review git diff**

Run: `git diff -- Documents/JarvisAssistant`
Expected: only Damien agent-spine files, targeted tests, settings, orchestrator, and app wiring changed.

- [ ] **Step 4: Commit implementation**

Run: `git add Documents/JarvisAssistant/src Documents/JarvisAssistant/tests Documents/JarvisAssistant/docs/superpowers/plans/2026-07-27-damien-agent-spine.md Documents/JarvisAssistant/docs/superpowers/specs/2026-07-27-damien-agent-spine-design.md && git commit -m "Implement Damien agent spine"`
Expected: commit succeeds with only relevant files staged.
