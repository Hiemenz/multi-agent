from __future__ import annotations

import asyncio
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

import aiofiles

from multi_agent.agents.base_agent import BaseAgent
from multi_agent.models.agent_result import AgentResult
from multi_agent.models.task import SubTask

logger = logging.getLogger(__name__)


class FileAgent(BaseAgent):
    """File CRUD agent with automatic backups and path traversal protection."""

    name = "file"

    def __init__(self, workspace_path: str = "./workspace", backup_path: str = "./backups") -> None:
        self._workspace = Path(workspace_path).resolve()
        self._backup = Path(backup_path).resolve()
        self._workspace.mkdir(parents=True, exist_ok=True)
        self._backup.mkdir(parents=True, exist_ok=True)

    async def execute(self, subtask: SubTask) -> AgentResult:
        meta = subtask.metadata
        operation = meta.get("operation", "read")
        rel_path = meta.get("path", "")
        content = meta.get("content", "")

        try:
            target = self._resolve_path(rel_path)
        except ValueError as exc:
            return AgentResult.fail(str(exc))

        if operation == "read":
            return await self._read(target)
        elif operation == "write":
            return await self._write(target, content)
        elif operation == "delete":
            return await self._delete(target)
        elif operation == "list":
            return await self._list(target)
        else:
            return AgentResult.fail(f"Unknown file operation: {operation!r}")

    def _resolve_path(self, rel_path: str) -> Path:
        target = (self._workspace / rel_path).resolve()
        if not str(target).startswith(str(self._workspace)):
            raise ValueError(f"Path traversal detected: {rel_path!r}")
        return target

    async def _read(self, path: Path) -> AgentResult:
        if not path.exists():
            return AgentResult.fail(f"File not found: {path}")
        async with aiofiles.open(path, "r") as f:
            content = await f.read()
        self.log(f"Read {path} ({len(content)} chars)")
        return AgentResult.ok(content, path=str(path))

    async def _write(self, path: Path, content: str) -> AgentResult:
        await self._backup_if_exists(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w") as f:
            await f.write(content)
        self.log(f"Wrote {path} ({len(content)} chars)")
        return AgentResult.ok(f"Written: {path}", path=str(path))

    async def _delete(self, path: Path) -> AgentResult:
        if not path.exists():
            return AgentResult.fail(f"File not found: {path}")
        await self._backup_if_exists(path)
        await asyncio.to_thread(path.unlink)
        self.log(f"Deleted {path}")
        return AgentResult.ok(f"Deleted: {path}", path=str(path))

    async def _list(self, path: Path) -> AgentResult:
        target = path if path.is_dir() else self._workspace
        entries = await asyncio.to_thread(lambda: [str(p.relative_to(self._workspace)) for p in target.iterdir()])
        return AgentResult.ok("\n".join(sorted(entries)))

    async def _backup_if_exists(self, path: Path) -> None:
        if path.exists():
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            backup_name = f"{ts}_{path.name}"
            dest = self._backup / backup_name
            await asyncio.to_thread(shutil.copy2, path, dest)
            self.log(f"Backed up {path.name} → {dest}")
