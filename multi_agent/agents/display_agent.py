from __future__ import annotations

import logging

from multi_agent.agents.base_agent import BaseAgent
from multi_agent.display.display_manager import DisplayManager
from multi_agent.display.image_builder import (
    build_complete_image,
    build_idle_image,
    build_progress_image,
    build_startup_image,
)
from multi_agent.models.agent_result import AgentResult
from multi_agent.models.task import SubTask, Task

logger = logging.getLogger(__name__)


class DisplayAgent(BaseAgent):
    """Bridges task state to the e-ink display."""

    name = "display"

    def __init__(self, display_manager: DisplayManager) -> None:
        self._dm = display_manager

    async def execute(self, subtask: SubTask) -> AgentResult:
        """Not used directly; use show_* methods instead."""
        return AgentResult.ok("Use show_* methods directly")

    async def show_startup(self) -> None:
        img = build_startup_image(self._dm.width, self._dm.height)
        await self._dm.show(img)

    async def show_idle(self) -> None:
        img = build_idle_image(self._dm.width, self._dm.height)
        await self._dm.show(img)

    async def show_task_progress(
        self,
        task: Task,
        agent_name: str = "",
        step_description: str = "",
        status_line: str = "",
    ) -> None:
        current = task.current_subtask
        agent = agent_name or (current.agent_type.value if current else "")
        step = step_description or (current.description if current else "")

        img = build_progress_image(
            width=self._dm.width,
            height=self._dm.height,
            task_description=task.description,
            agent_name=agent,
            step_description=step,
            progress_pct=task.progress_pct,
            status_line=status_line,
        )
        await self._dm.show(img)

    async def show_complete(self, task: Task) -> None:
        img = build_complete_image(self._dm.width, self._dm.height, task.description)
        await self._dm.show(img)

    async def show_waiting_approval(self, task: Task, step_description: str) -> None:
        img = build_progress_image(
            width=self._dm.width,
            height=self._dm.height,
            task_description=task.description,
            agent_name="approval",
            step_description=step_description,
            progress_pct=task.progress_pct,
            status_line="⏳ Waiting for human approval in Slack...",
        )
        await self._dm.show(img)
