from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ApprovalGate:
    """
    Manages async approval/rejection flows.

    One asyncio.Future per pending subtask ID.
    Resolved by Slack button callbacks (approve_action / reject_action).
    """

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[bool]] = {}

    async def wait(self, request_id: str, timeout: float = 300.0) -> bool:
        """
        Create a future for request_id and wait up to `timeout` seconds.
        Returns True if approved, False if rejected or timed out.
        """
        loop = asyncio.get_event_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending[request_id] = future
        logger.info("ApprovalGate: waiting for %s (timeout=%ss)", request_id, timeout)
        try:
            result = await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning("ApprovalGate: timeout for %s", request_id)
            return False
        finally:
            self._pending.pop(request_id, None)

    def resolve(self, request_id: str, approved: bool) -> bool:
        """
        Called from Slack button handler to resolve a pending request.
        Returns True if the future was found and resolved, False if not found.
        """
        future = self._pending.get(request_id)
        if future is None:
            logger.warning("ApprovalGate: no pending request for %s", request_id)
            return False
        if not future.done():
            future.set_result(approved)
            logger.info("ApprovalGate: resolved %s → approved=%s", request_id, approved)
            return True
        return False

    def has_pending(self, request_id: str) -> bool:
        return request_id in self._pending
