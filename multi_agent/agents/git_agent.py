from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import git

from multi_agent.agents.base_agent import BaseAgent
from multi_agent.llm.gemini_client import GeminiClient
from multi_agent.models.agent_result import AgentResult
from multi_agent.models.task import SubTask

logger = logging.getLogger(__name__)

_COMMIT_MSG_PROMPT = """You are a git commit message expert.
Write a concise, imperative commit message (max 72 chars on the first line)
based on the following staged diff. Optionally add a blank line and body.

Diff:
{diff}

Return ONLY the commit message text, no extra commentary.
"""


class GitAgent(BaseAgent):
    """Git operations agent. git push always requires approval."""

    name = "git"

    def __init__(self, gemini: GeminiClient, workspace_path: str = "./workspace") -> None:
        self._gemini = gemini
        self._workspace = Path(workspace_path).resolve()

    async def execute(self, subtask: SubTask) -> AgentResult:
        meta = subtask.metadata
        operation = meta.get("operation", "status")
        repo_path = meta.get("repo_path", str(self._workspace))

        # git push always requires approval — enforce it here too
        if operation == "push":
            subtask.requires_approval = True

        try:
            repo = await asyncio.to_thread(git.Repo, repo_path)
        except git.InvalidGitRepositoryError:
            return AgentResult.fail(f"Not a git repository: {repo_path}")

        if operation == "status":
            return await self._status(repo)
        elif operation == "add":
            paths = meta.get("paths", ["."])
            return await self._add(repo, paths)
        elif operation == "commit":
            msg = meta.get("message", "")
            return await self._commit(repo, msg)
        elif operation == "push":
            remote = meta.get("remote", "origin")
            branch = meta.get("branch", "")
            return await self._push(repo, remote, branch)
        elif operation == "diff":
            return await self._diff(repo)
        elif operation == "log":
            n = meta.get("n", 5)
            return await self._log(repo, n)
        else:
            return AgentResult.fail(f"Unknown git operation: {operation!r}")

    async def _status(self, repo: git.Repo) -> AgentResult:
        status = await asyncio.to_thread(lambda: repo.git.status())
        return AgentResult.ok(status)

    async def _diff(self, repo: git.Repo) -> AgentResult:
        diff = await asyncio.to_thread(lambda: repo.git.diff("--cached") or repo.git.diff())
        return AgentResult.ok(diff)

    async def _add(self, repo: git.Repo, paths: list[str]) -> AgentResult:
        await asyncio.to_thread(repo.index.add, paths)
        return AgentResult.ok(f"Staged: {paths}")

    async def _commit(self, repo: git.Repo, message: str) -> AgentResult:
        if not message:
            # Auto-generate commit message from staged diff
            diff = await asyncio.to_thread(lambda: repo.git.diff("--cached"))
            truncated = diff[:4000] if len(diff) > 4000 else diff
            if truncated.strip():
                prompt = _COMMIT_MSG_PROMPT.format(diff=truncated)
                try:
                    message = await self._gemini.generate(prompt)
                    message = message.strip()
                except Exception as exc:
                    message = "Auto-commit"
                    self.log(f"Commit message generation failed: {exc}", logging.WARNING)
            else:
                message = "Auto-commit: no staged changes detected"

        commit = await asyncio.to_thread(repo.index.commit, message)
        return AgentResult.ok(f"Committed: {commit.hexsha[:7]} — {message[:60]}")

    async def _push(self, repo: git.Repo, remote: str, branch: str) -> AgentResult:
        origin = repo.remote(remote)
        push_args = [branch] if branch else []
        push_info = await asyncio.to_thread(origin.push, *push_args)
        return AgentResult.ok(f"Pushed to {remote}/{branch or 'default'}")

    async def _log(self, repo: git.Repo, n: int) -> AgentResult:
        commits = list(repo.iter_commits(max_count=n))
        lines = [f"{c.hexsha[:7]} {c.summary}" for c in commits]
        return AgentResult.ok("\n".join(lines))
