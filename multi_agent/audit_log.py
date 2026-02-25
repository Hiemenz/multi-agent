from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiofiles

logger = logging.getLogger(__name__)


class AuditLogger:
    def __init__(self, log_path: str = "./logs/audit.jsonl"):
        self._path = Path(log_path)
        self._lock = asyncio.Lock()

    async def setup(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def log(
        self,
        event: str,
        task_id: Optional[str] = None,
        subtask_id: Optional[str] = None,
        agent: Optional[str] = None,
        success: Optional[bool] = None,
        details: Optional[dict] = None,
        **extra: Any,
    ) -> None:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
        }
        if task_id:
            entry["task_id"] = task_id
        if subtask_id:
            entry["subtask_id"] = subtask_id
        if agent:
            entry["agent"] = agent
        if success is not None:
            entry["success"] = success
        if details:
            entry["details"] = details
        entry.update(extra)

        line = json.dumps(entry) + "\n"
        async with self._lock:
            try:
                async with aiofiles.open(self._path, "a") as f:
                    await f.write(line)
            except Exception as exc:
                logger.error("AuditLogger write failed: %s", exc)
