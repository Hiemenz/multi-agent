from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Optional

from multi_agent.agents.base_agent import BaseAgent
from multi_agent.agents.code_agent import CodeAgent
from multi_agent.agents.display_agent import DisplayAgent
from multi_agent.agents.file_agent import FileAgent
from multi_agent.agents.git_agent import GitAgent
from multi_agent.agents.test_agent import TestAgent
from multi_agent.audit_log import AuditLogger
from multi_agent.llm.gemini_client import GeminiClient
from multi_agent.models.agent_result import AgentResult
from multi_agent.models.task import AgentType, SubTask, Task, TaskStatus

if TYPE_CHECKING:
    from multi_agent.slack.approval_gate import ApprovalGate

logger = logging.getLogger(__name__)

_DECOMPOSE_PROMPT = """You are a task decomposition expert for an autonomous multi-agent system.

Break down the following task into a list of concrete subtasks.
Each subtask must be handled by exactly one of these agents:
  - code: Generate or modify code
  - file: Read, write, delete, or list files in the workspace
  - git: Git operations (status, add, commit, push, diff, log)
  - test: Run pytest tests

For each subtask return a JSON object with:
  - description: Clear, actionable description of what this subtask does
  - agent_type: one of "code", "file", "git", "test"
  - requires_approval: true only for destructive/irreversible operations (git push, file delete)
  - metadata: dict with agent-specific parameters (e.g. {{"operation": "write", "path": "foo.py"}})

Return a JSON array of subtask objects. No other text.

Task: {task_description}
"""


class OrchestratorAgent(BaseAgent):
    """Decomposes tasks and coordinates all sub-agents."""

    name = "orchestrator"

    def __init__(
        self,
        gemini: GeminiClient,
        display_agent: DisplayAgent,
        audit_logger: AuditLogger,
        workspace_path: str = "./workspace",
        backup_path: str = "./backups",
        approval_gate: Optional["ApprovalGate"] = None,
        slack_post_fn: Optional[Callable] = None,
    ) -> None:
        self._gemini = gemini
        self._display = display_agent
        self._audit = audit_logger
        self._approval_gate = approval_gate
        self._slack_post = slack_post_fn  # async fn(channel, thread_ts, text)

        # Sub-agents
        self._code_agent = CodeAgent(gemini)
        self._file_agent = FileAgent(workspace_path, backup_path)
        self._git_agent = GitAgent(gemini, workspace_path)
        self._test_agent = TestAgent(workspace_path)

    async def execute(self, subtask: SubTask) -> AgentResult:
        """Not used directly; call run_task() instead."""
        return AgentResult.ok("Use run_task() to orchestrate a full task")

    async def run_task(self, task: Task) -> None:
        """Main orchestration loop for a task."""
        task.status = TaskStatus.IN_PROGRESS
        task.created_at = datetime.now(timezone.utc).isoformat()

        await self._audit.log("task_start", task_id=task.id, details={"description": task.description})
        await self._display.show_task_progress(task, agent_name="orchestrator", step_description="Decomposing task...")

        # Step 1: decompose
        try:
            subtasks = await self._decompose(task)
        except Exception as exc:
            logger.error("Task decomposition failed: %s", exc)
            task.status = TaskStatus.FAILED
            await self._audit.log("task_failed", task_id=task.id, details={"error": str(exc)})
            await self._post_slack(task, f":x: Task decomposition failed: {exc}")
            return

        task.subtasks = subtasks
        logger.info("Decomposed into %d subtasks", len(subtasks))
        await self._post_slack(task, f":white_check_mark: Decomposed into {len(subtasks)} subtasks. Starting execution...")

        # Step 2: execute each subtask
        for i, st in enumerate(subtasks):
            task.current_subtask_index = i
            st.status = TaskStatus.IN_PROGRESS

            await self._display.show_task_progress(task)
            await self._audit.log(
                "subtask_start",
                task_id=task.id,
                subtask_id=st.id,
                agent=st.agent_type.value,
                details={"description": st.description},
            )

            # Approval gate for destructive operations
            if st.requires_approval and self._approval_gate:
                await self._display.show_waiting_approval(task, st.description)
                approved = await self._request_approval(task, st)
                if not approved:
                    st.status = TaskStatus.REJECTED
                    st.error = "Rejected by user"
                    await self._audit.log("subtask_rejected", task_id=task.id, subtask_id=st.id)
                    await self._post_slack(task, f":no_entry: Subtask rejected: _{st.description}_")
                    continue

            # Dispatch to appropriate agent
            result = await self._dispatch(st)

            # Record result
            st.result = result.output
            if result.success:
                st.status = TaskStatus.COMPLETED
                await self._audit.log(
                    "subtask_complete",
                    task_id=task.id,
                    subtask_id=st.id,
                    agent=st.agent_type.value,
                    success=True,
                )
            else:
                st.status = TaskStatus.FAILED
                st.error = result.error
                await self._audit.log(
                    "subtask_failed",
                    task_id=task.id,
                    subtask_id=st.id,
                    agent=st.agent_type.value,
                    success=False,
                    details={"error": result.error},
                )
                await self._post_slack(task, f":warning: Subtask failed: _{st.description}_\n```{result.error}```")

        # Step 3: finalize
        task.completed_at = datetime.now(timezone.utc).isoformat()
        all_ok = all(st.status == TaskStatus.COMPLETED for st in subtasks)
        task.status = TaskStatus.COMPLETED if all_ok else TaskStatus.FAILED

        if all_ok:
            await self._display.show_complete(task)
        else:
            await self._display.show_task_progress(task, status_line="Task finished with errors")

        summary = self._build_summary(task)
        await self._audit.log("task_complete", task_id=task.id, success=all_ok)
        await self._post_slack(task, summary)

    async def _decompose(self, task: Task) -> list[SubTask]:
        prompt = _DECOMPOSE_PROMPT.format(task_description=task.description)
        raw = await self._gemini.generate_json(prompt)

        subtasks: list[SubTask] = []
        for item in raw:
            agent_str = item.get("agent_type", "code")
            try:
                agent_type = AgentType(agent_str)
            except ValueError:
                agent_type = AgentType.CODE

            st = SubTask(
                description=item.get("description", ""),
                agent_type=agent_type,
                requires_approval=item.get("requires_approval", False),
                metadata=item.get("metadata", {}),
            )
            subtasks.append(st)
        return subtasks

    async def _dispatch(self, subtask: SubTask) -> AgentResult:
        agent_map: dict[AgentType, BaseAgent] = {
            AgentType.CODE: self._code_agent,
            AgentType.FILE: self._file_agent,
            AgentType.GIT: self._git_agent,
            AgentType.TEST: self._test_agent,
        }
        agent = agent_map.get(subtask.agent_type, self._code_agent)
        try:
            return await agent.execute(subtask)
        except Exception as exc:
            logger.error("Agent %s raised exception: %s", subtask.agent_type, exc)
            return AgentResult.fail(str(exc))

    async def _request_approval(self, task: Task, subtask: SubTask) -> bool:
        if not self._approval_gate:
            return True  # no gate configured → auto-approve

        from multi_agent.slack.message_builder import build_approval_message

        # Post approval request to Slack
        if self._slack_post:
            blocks = build_approval_message(task, subtask)
            await self._slack_post(
                channel=task.slack_channel,
                thread_ts=task.slack_thread_ts,
                text=f"Approval needed: {subtask.description}",
                blocks=blocks,
                approval_id=subtask.id,
            )

        try:
            approved = await self._approval_gate.wait(subtask.id, timeout=300)
            return approved
        except asyncio.TimeoutError:
            logger.warning("Approval timed out for subtask %s", subtask.id)
            return False

    async def _post_slack(self, task: Task, text: str) -> None:
        if self._slack_post and task.slack_channel:
            try:
                await self._slack_post(
                    channel=task.slack_channel,
                    thread_ts=task.slack_thread_ts,
                    text=text,
                )
            except Exception as exc:
                logger.warning("Slack post failed: %s", exc)

    def _build_summary(self, task: Task) -> str:
        lines = [f":clipboard: *Task Complete*: {task.description}", ""]
        for i, st in enumerate(task.subtasks, 1):
            icon = ":white_check_mark:" if st.status == TaskStatus.COMPLETED else \
                   ":no_entry:" if st.status == TaskStatus.REJECTED else ":x:"
            lines.append(f"{icon} `{st.agent_type.value.upper()}` {st.description[:80]}")
        lines.append(f"\nProgress: {task.progress_pct}%")
        return "\n".join(lines)
