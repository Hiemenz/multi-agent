from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from multi_agent.models.agent_result import AgentResult
from multi_agent.models.task import SubTask


logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    name: str = "base"

    @abstractmethod
    async def execute(self, subtask: SubTask) -> AgentResult:
        """Execute the subtask and return a result."""
        ...

    def log(self, msg: str, level: int = logging.DEBUG) -> None:
        logger.log(level, "[%s] %s", self.name.upper(), msg)
