# Damien Agent Spine Design

## Purpose

Damien should become a voice-first PC companion, not a pile of scripts behind command phrases. The assistant should feel device-native and immediate: the user talks to Damien, Damien responds aloud, uses approved device capabilities, remembers useful context, creates notes and reminders, notices opportunities to help, and can later think on another machine without changing the user experience.

The first implementation should build the agent spine that makes this possible while keeping the current app usable. Existing commands remain valuable, but they move behind a cleaner agent/tool boundary instead of being Damien's whole brain.

## Product Direction

Damien is voice-first. The desktop window and tray remain important for setup, visibility, history, settings, diagnostics, and manual fallback, but the primary interaction is spoken:

1. The user speaks to Damien.
2. Damien transcribes the request.
3. Damien gathers relevant context.
4. Damien decides whether to answer, act, ask a follow-up, save information, create a reminder, or queue an upgrade.
5. Damien executes approved low-risk actions.
6. Damien verifies what happened when possible.
7. Damien responds naturally aloud.

Damien should also be active by default. He should speak up when useful, especially for reminders, failed actions, unfinished tasks, and repeated routines. The proactive behavior must be trainable: the user can say "not now," "stop suggesting that," "remind me later," or "be quiet for an hour."

## Provider Model

Damien is free-first and provider-flexible.

The first implementation keeps the brain on the current PC using the existing Ollama path. The architecture must not assume that the model always lives on the same machine. A later configuration should allow the brain to run on an Ubuntu laptop or server on the user's local network, while the PC app keeps local device access and performs local actions.

Paid services are not part of the first implementation. Future paid providers may be supported only when they are explicitly approved by the user, cheap enough to be worth discussing, and disabled by default.

Provider requirements:

- Default to free providers.
- Support local Ollama at `http://127.0.0.1:11434`.
- Keep the provider URL configurable so a later LAN Ollama or brain service can be used.
- Keep tool execution on the user's device behind Damien's safety policy.
- Do not make the user interact through a website. Network addresses are internal plumbing only.

## Architecture

Add an agent runtime between user input and the existing command/tool code.

Current simplified flow:

```text
text -> regex plan -> execute or chat
```

Target flow:

```text
voice/text -> context snapshot -> intent/task plan -> action or answer -> verification -> spoken response
```

### AgentRuntime

Owns a single assistant turn from input to final response.

Responsibilities:

- Accept text from voice, typed chat, remote input, or future device clients.
- Build a context snapshot.
- Ask the planner what to do.
- Execute approved actions through the tool executor.
- Save notes, reminders, and memory updates through dedicated stores.
- Trigger verification when an action claims to affect the PC.
- Return a response suitable for speech and chat history.

### ContextCollector

Builds a small, bounded context snapshot for each turn.

Phase one context:

- Current user utterance.
- Recent conversation history.
- Enabled settings relevant to routing, voice, memory, reminders, and proactive behavior.
- Available tools and their risk level.
- Recent failed actions and queued improvement records.
- Due or pending reminders.
- Notes and memory summaries when relevant.
- Screen summary only when explicitly requested or when a verifier needs it.

Future context:

- Calendar/email summaries.
- Phone/device presence.
- Browser state.
- Larger project/task state.
- More detailed active window/app state.

### IntentPlanner

Decides the next assistant move.

Planner outputs:

- `answer`: respond without tools.
- `use_tool`: execute one approved tool.
- `use_tools`: execute multiple low-risk tools in order.
- `ask_followup`: ask the user for missing information.
- `save_note`: store user-provided note content.
- `create_reminder`: create a reminder with parsed timing and message.
- `dismiss_or_complete_reminder`: mark a reminder handled.
- `proactive_suggestion`: speak up because an ambient trigger found something useful.
- `queue_upgrade`: log a missing capability for Codex.
- `refuse`: explain why a request is blocked.

The existing regex-based `ToolRegistry.plan()` becomes a fast path and tool candidate source. It should not be the only path. If a command is obvious, the fast path can still win. If the request is ambiguous, multi-step, reminder-like, note-like, or proactive, the agent planner handles it.

### ToolExecutor

Runs tools through the existing risk policy.

Requirements:

- Low-risk actions may run automatically.
- Important actions require confirmation.
- Dangerous actions are denied.
- Tool results include whether execution actually happened.
- Tool results include enough detail for the verifier and audit log.
- Existing tools should be adapted incrementally rather than rewritten all at once.

### Verifier

Checks whether an action likely worked before Damien claims success.

Phase one verification:

- For reminder and note actions, verify by reading the store after write.
- For app/tool actions, keep current result strings but add a verification hook field so stronger checks can be added later.
- For screen actions, use existing screen access only when the user requested screen interaction or the tool specifically needs it.
- For failed or uncertain actions, Damien should say what he knows instead of pretending.

Future verification:

- Active window detection.
- Browser state checks.
- App-specific state checks.
- Device-client confirmations.

## Notes

Notes become a first-class agent surface instead of only a convenience command.

Phase one requirements:

- Save notes from natural spoken commands.
- List recent notes.
- Search notes by simple text.
- Use notes as context when a user asks about saved information.
- Store notes locally in an inspectable format.
- Preserve current note behavior where possible.

Notes are not full long-term memory. They are explicit user records. Damien may suggest saving something as a note, but should not silently store sensitive content.

## Reminders

Add a local reminder system.

Phase one reminder capabilities:

- Create reminders from spoken text with simple time expressions.
- List pending reminders.
- Dismiss or complete reminders.
- Check due reminders in the background.
- Speak due reminders when proactive behavior is enabled.
- Avoid repeating dismissed reminders.
- Persist reminders locally in an inspectable format.

Supported first-pass time expressions:

- Absolute times today, such as "at 5 PM."
- Relative times, such as "in 20 minutes."
- Simple dates, such as "tomorrow at 3."

If Damien cannot parse the time safely, he should ask a follow-up instead of guessing.

## Ambient Loop

Add a lightweight proactive loop that runs while Damien is active.

Phase one triggers:

- Due reminders.
- Failed actions that have not been acknowledged.
- Unfinished tasks created by the new agent runtime.
- Repeated routines that are obvious from local history, such as repeatedly opening the same app group.

Default behavior is active and spoken. Damien should speak up when useful, with guardrails:

- Do not interrupt fullscreen games unless the reminder is urgent or the user allows it.
- Do not speak over media unless the reminder/action is important.
- Do not repeat a suggestion after dismissal.
- Respect "not now," "stop suggesting that," "remind me later," and "be quiet for an hour."
- Log why Damien spoke up so behavior can be tuned.

Phase one can implement only the simplest reliable triggers. The important architecture point is that proactive behavior is owned by the agent runtime, not scattered across unrelated command handlers.

## Future Capabilities Designed In

The overall Damien rework includes these future directions, but they are not all implemented in the first slice:

- Phone or companion device clients.
- Calendar integration.
- Email integration.
- Autonomous web browsing and research.
- Larger task and project management.
- Server-hosted brain service.

The first implementation should create extension points for these:

- Calendar/email as future life context providers.
- Phone/device clients as future input/output and confirmation surfaces.
- Browser automation as a future agent tool.
- Multi-day projects as a future goal/task memory layer.
- Server thinking as a future provider deployment, not a new user interface.

Server deployment itself is explicitly not part of the first implementation.

## Safety And Privacy

Damien should feel capable, but the user stays in control.

Rules:

- Keep existing dangerous-action denials.
- Keep important-action confirmation gates.
- Do not silently buy, delete, install, send messages, submit forms, expose credentials, or change important system settings.
- Keep reminders and notes local and inspectable in phase one.
- Do not save raw microphone audio by default.
- Do not require paid services.
- Audit actions, proactive triggers, reminders, and failed action notices.

Proactive speech is allowed by default because the user asked for Damien to be active and speak up. The user must have simple voice controls to pause or tune that behavior.

## First Implementation Slice

Implement Agent Spine + Notes/Reminders/Proactive v1.

Included:

- `AgentRuntime` turn orchestration.
- `ContextCollector` with bounded local context.
- `IntentPlanner` result types.
- Adapter from existing `ToolRegistry` into the new runtime.
- Reminder store and reminder parser for simple time expressions.
- Note store improvements for save/list/search.
- Ambient loop for due reminders, failed actions, unfinished tasks, and simple repeated-routine suggestions.
- Spoken responses that remain short, natural, and voice-first.
- Settings for proactive behavior and reminder checks.
- Tests for new agent decisions and backward compatibility.

Not included in the first implementation:

- Phone companion implementation.
- Calendar/email implementation.
- Full autonomous web agent.
- Full project-management system.
- Server deployment.
- Paid provider integration.

## Testing

Add focused tests for:

- Agent runtime routing direct answers versus tool actions.
- Existing command compatibility through the new runtime.
- Reminder creation, listing, completion, and due checks.
- Reminder parse failures that ask follow-up questions.
- Note save, list, and search behavior.
- Proactive trigger selection and dismissal behavior.
- Failed action notice behavior.
- Provider settings remaining free-first and local by default.
- Safety policy preserving denial and confirmation behavior.

Existing tests for tools, orchestration, speech, memory, startup, and audit should continue to pass or be updated intentionally when the new runtime replaces the old path.

## Approval Gate

This design document is not implementation approval.

Before coding begins, ask the user to approve the single implementation task:

```text
Approve starting implementation of Agent Spine + Notes/Reminders/Proactive v1?
```

After that approval, normal smaller implementation decisions can proceed without repeatedly asking, unless a change is destructive, paid, privacy-sensitive, or outside the approved task.
