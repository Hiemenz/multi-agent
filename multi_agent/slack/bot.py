from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from multi_agent.audit_log import AuditLogger
from multi_agent.config import AppConfig
from multi_agent.models.task import Task
from multi_agent.slack.approval_gate import ApprovalGate
from multi_agent.slack.message_builder import build_ack_message, build_error_message

logger = logging.getLogger(__name__)


class SlackBot:
    """
    Slack Socket Mode bot.

    Listens for @mentions, creates Tasks, launches the orchestrator.
    Handles Approve/Reject button callbacks via ApprovalGate.
    """

    def __init__(
        self,
        config: AppConfig,
        audit_logger: AuditLogger,
        approval_gate: ApprovalGate,
        orchestrator_factory,  # callable(task) -> coroutine
    ) -> None:
        self._config = config
        self._audit = audit_logger
        self._gate = approval_gate
        self._orchestrator_factory = orchestrator_factory

        self._app = AsyncApp(token=config.slack.bot_token)
        self._handler: Optional[AsyncSocketModeHandler] = None

        self._register_handlers()

    def _register_handlers(self) -> None:
        @self._app.event("app_mention")
        async def handle_mention(event: dict, say, client) -> None:
            await self._on_mention(event, say, client)

        @self._app.action("approve_action")
        async def handle_approve(ack, body, client) -> None:
            await ack()
            await self._on_approval(body, client, approved=True)

        @self._app.action("reject_action")
        async def handle_reject(ack, body, client) -> None:
            await ack()
            await self._on_approval(body, client, approved=False)

    async def _on_mention(self, event: dict, say, client) -> None:
        text: str = event.get("text", "")
        channel: str = event.get("channel", "")
        thread_ts: str = event.get("thread_ts") or event.get("ts", "")
        user: str = event.get("user", "")

        # Strip bot mention from text
        description = _strip_mention(text).strip()
        if not description:
            await say(text="Please provide a task description after the @mention.", thread_ts=thread_ts)
            return

        task = Task(
            description=description,
            slack_channel=channel,
            slack_thread_ts=thread_ts,
            slack_user=user,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        ack_msg = build_ack_message(task)
        await say(text=ack_msg, thread_ts=thread_ts)
        await self._audit.log("task_received", task_id=task.id, details={"user": user, "description": description})

        # Launch orchestrator as a background task — do NOT await here
        # so the event loop remains free for button clicks during execution
        asyncio.create_task(self._run_orchestrator(task, client))

    async def _run_orchestrator(self, task: Task, client) -> None:
        try:
            orchestrator = self._orchestrator_factory(
                slack_post_fn=self._make_post_fn(client),
            )
            await orchestrator.run_task(task)
        except Exception as exc:
            logger.error("Orchestrator error for task %s: %s", task.id, exc)
            try:
                await client.chat_postMessage(
                    channel=task.slack_channel,
                    thread_ts=task.slack_thread_ts,
                    text=build_error_message(str(exc)),
                )
            except Exception:
                pass

    async def _on_approval(self, body: dict, client, approved: bool) -> None:
        action = body.get("actions", [{}])[0]
        subtask_id = action.get("value", "")
        user_id = body.get("user", {}).get("id", "unknown")

        resolved = self._gate.resolve(subtask_id, approved)
        label = "Approved" if approved else "Rejected"

        # Update the original message to show the decision
        try:
            message = body.get("message", {})
            channel = body.get("channel", {}).get("id", "")
            ts = message.get("ts", "")
            if channel and ts:
                await client.chat_update(
                    channel=channel,
                    ts=ts,
                    text=f"{label} by <@{user_id}>",
                    blocks=[
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": (
                                    f"{'✅' if approved else '❌'} *{label}* by <@{user_id}>"
                                ),
                            },
                        }
                    ],
                )
        except Exception as exc:
            logger.warning("Failed to update approval message: %s", exc)

        await self._audit.log(
            "approval_resolved",
            details={"subtask_id": subtask_id, "approved": approved, "user": user_id},
        )

    def _make_post_fn(self, client):
        async def post(channel: str, thread_ts: str, text: str, blocks=None, approval_id=None):
            kwargs: dict[str, Any] = {
                "channel": channel,
                "text": text,
            }
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            if blocks:
                kwargs["blocks"] = blocks
            await client.chat_postMessage(**kwargs)
        return post

    async def start(self) -> None:
        self._handler = AsyncSocketModeHandler(self._app, self._config.slack.app_token)
        logger.info("Starting Slack Socket Mode bot...")
        await self._handler.start_async()

    async def stop(self) -> None:
        if self._handler:
            await self._handler.close_async()


def _strip_mention(text: str) -> str:
    """Remove <@USERID> mention patterns from the start of the text."""
    import re
    return re.sub(r"^<@[A-Z0-9]+>\s*", "", text).strip()
