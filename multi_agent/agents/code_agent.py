from __future__ import annotations

import logging

from multi_agent.agents.base_agent import BaseAgent
from multi_agent.llm.gemini_client import GeminiClient
from multi_agent.models.agent_result import AgentResult
from multi_agent.models.task import SubTask

logger = logging.getLogger(__name__)

_CODE_SYSTEM_PROMPT = """You are an expert software engineer.
Generate clean, production-ready code based on the user's request.
Return ONLY the code (no explanations unless specifically asked).
If the task asks for multiple files, clearly separate them with a comment like:
# === FILE: path/to/file.py ===
"""


class CodeAgent(BaseAgent):
    """Gemini-powered code generation agent."""

    name = "code"

    def __init__(self, gemini: GeminiClient) -> None:
        self._gemini = gemini

    async def execute(self, subtask: SubTask) -> AgentResult:
        prompt = f"{_CODE_SYSTEM_PROMPT}\n\nTask: {subtask.description}"
        try:
            code = await self._gemini.generate(prompt)
            self.log(f"Generated {len(code)} chars of code")
            return AgentResult.ok(code)
        except Exception as exc:
            self.log(f"Code generation failed: {exc}", logging.ERROR)
            return AgentResult.fail(str(exc))
