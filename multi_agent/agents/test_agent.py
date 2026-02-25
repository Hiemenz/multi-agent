from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from multi_agent.agents.base_agent import BaseAgent
from multi_agent.models.agent_result import AgentResult
from multi_agent.models.task import SubTask

logger = logging.getLogger(__name__)


class TestAgent(BaseAgent):
    """Runs pytest in a subprocess and returns the output."""

    name = "test"

    def __init__(self, workspace_path: str = "./workspace") -> None:
        self._workspace = Path(workspace_path).resolve()

    async def execute(self, subtask: SubTask) -> AgentResult:
        meta = subtask.metadata
        test_path = meta.get("test_path", "tests/")
        extra_args = meta.get("args", ["-v"])
        cwd = meta.get("cwd", str(self._workspace))

        cmd = ["python", "-m", "pytest", test_path, *extra_args]
        self.log(f"Running: {' '.join(cmd)} in {cwd}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode("utf-8", errors="replace")
            success = proc.returncode == 0
            self.log(f"Tests {'passed' if success else 'failed'} (exit {proc.returncode})")
            return AgentResult(success=success, output=output, error=None if success else f"Exit code {proc.returncode}")
        except Exception as exc:
            self.log(f"Test runner error: {exc}", logging.ERROR)
            return AgentResult.fail(str(exc))
