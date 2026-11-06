from __future__ import annotations

from ..audit import AuditEvent, AuditLogger
from ..tools import PlannedTool, RiskLevel, ToolRegistry, ToolResult
from .proactive import UnfinishedTaskStore


class ToolExecutionService:
    def __init__(self, tools: ToolRegistry, audit: AuditLogger, unfinished_tasks: UnfinishedTaskStore | None = None) -> None:
        self.tools = tools
        self.audit = audit
        self.unfinished_tasks = unfinished_tasks

    def execute_many(
        self,
        plans: list[PlannedTool],
        *,
        user_request: str,
        provider: str,
        cloud_data_sent: bool,
        outcome: str,
    ) -> list[ToolResult]:
        results = [self.tools.execute(planned) for planned in plans]
        audit_request = _audit_safe_request(user_request, [result.name for result in results])
        self.audit.log(
            AuditEvent(
                user_request=audit_request,
                provider=provider,
                tools_called=[result.name for result in results],
                cloud_data_sent=cloud_data_sent,
                confirmations_requested=[result.name for result in results if result.confirmation_required],
                outcome=outcome,
            )
        )
        for result in results:
            self._record_unfinished_if_needed(result, user_request)
        return results

    def execute_one(
        self,
        planned: PlannedTool,
        *,
        user_request: str,
        provider: str,
        cloud_data_sent: bool,
        outcome: str | None = None,
        outcome_prefix: str = "",
    ) -> ToolResult:
        result = self.tools.execute(planned)
        if planned.name == "powershell_confirmation":
            final_outcome = "PowerShell confirmation requested; command omitted from audit log."
        elif outcome is not None:
            final_outcome = outcome
        elif result.name == "run_powershell":
            final_outcome = "PowerShell command executed; output omitted from audit log."
        else:
            final_outcome = f"{outcome_prefix}{result.content}"
        self.audit.log(
            AuditEvent(
                user_request=_audit_safe_request(user_request, [result.name]),
                provider=provider,
                tools_called=[result.name],
                cloud_data_sent=cloud_data_sent,
                confirmations_requested=[result.name] if result.confirmation_required else [],
                outcome=final_outcome[:500],
            )
        )
        self._record_unfinished_if_needed(result, user_request)
        return result

    def _record_unfinished_if_needed(self, result: ToolResult, user_request: str) -> None:
        if self.unfinished_tasks is None:
            return
        executed = bool(getattr(result, "executed", True))
        confirmation_required = bool(getattr(result, "confirmation_required", False))
        risk = getattr(result, "risk", None)
        if executed or confirmation_required or risk == RiskLevel.DENY:
            return
        self.unfinished_tasks.add(f"Follow up on: {user_request}", result.content)


def _audit_safe_request(user_request: str, result_names: list[str]) -> str:
    if any(name in {"powershell_confirmation", "run_powershell"} for name in result_names):
        return "PowerShell command requested or confirmed; command omitted from audit log."
    return user_request
