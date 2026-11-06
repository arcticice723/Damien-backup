from __future__ import annotations

from ..ai import ChatMessage
from ..interpretation import Interpretation, UtteranceInterpreter
from ..improvement import UpgradeIntentHandler
from ..tools import ToolRegistry, ToolResult
from .multitask import MultitaskPlanner
from .runtime_result import AgentTurnResult
from .tool_execution import ToolExecutionService


class CommandResponder:
    def __init__(
        self,
        tools: ToolRegistry,
        execution: ToolExecutionService,
        multitask_planner: MultitaskPlanner,
        upgrade_intents: UpgradeIntentHandler,
        interpreter: UtteranceInterpreter | None = None,
        persona_style: str = "cinematic",
    ) -> None:
        self.tools = tools
        self.execution = execution
        self.multitask_planner = multitask_planner
        self.upgrade_intents = upgrade_intents
        self.interpreter = interpreter or UtteranceInterpreter()
        self.persona_style = persona_style

    def respond(
        self,
        text: str,
        base_messages: list[ChatMessage],
        provider: str,
        cloud_data_sent: bool,
    ) -> AgentTurnResult | None:
        multitask = self.multitask_planner.plan(text)
        if multitask:
            results = self.execution.execute_many(
                multitask,
                user_request=text,
                provider=provider,
                cloud_data_sent=cloud_data_sent,
                outcome="Executed multitask command.",
            )
            return AgentTurnResult(
                provider=provider,
                messages=base_messages,
                direct_response="\n".join(result.content for result in results),
                tool_results=results,
                cloud_data_sent=cloud_data_sent,
            )

        planned = self.tools.plan(text)
        interpretation: Interpretation | None = None
        if planned is None:
            interpretation = self.interpreter.interpret(text)
            if interpretation.changed:
                planned = self.tools.plan(interpretation.corrected)
        if planned is None:
            response = self.upgrade_intents.handle(text)
            if response is None:
                return None
            return AgentTurnResult(
                provider=provider,
                messages=base_messages,
                direct_response=response,
                cloud_data_sent=cloud_data_sent,
                interpretation=interpretation,
            )

        result = self.execution.execute_one(
            planned,
            user_request=text,
            provider=provider,
            cloud_data_sent=cloud_data_sent,
            outcome_prefix=_audit_prefix(interpretation),
        )
        tool_results: list[ToolResult] = [result]
        if result.risk.value in {"low", "deny"} or result.confirmation_required:
            return AgentTurnResult(
                provider=provider,
                messages=base_messages,
                direct_response=_voice_preface(result.content, self.persona_style),
                tool_results=tool_results,
                cloud_data_sent=cloud_data_sent,
                interpretation=interpretation,
            )
        return AgentTurnResult(
            provider=provider,
            messages=base_messages,
            tool_results=tool_results,
            cloud_data_sent=cloud_data_sent,
            interpretation=interpretation,
        )


def _voice_preface(content: str, persona_style: str) -> str:
    if persona_style != "cinematic":
        return content
    if content.startswith(("Denied:", "Confirmation required:", "Opening", "Logged", "Inspectable", "Approved", "System", "Web")):
        return content
    return content


def _audit_prefix(interpretation: Interpretation | None) -> str:
    if interpretation and interpretation.changed:
        return f"Interpreted as {interpretation.corrected!r}. "
    return ""
