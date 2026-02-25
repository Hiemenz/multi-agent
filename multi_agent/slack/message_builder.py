from __future__ import annotations

from typing import Any

from multi_agent.models.task import SubTask, Task


def build_approval_message(task: Task, subtask: SubTask) -> list[dict[str, Any]]:
    """Build Block Kit JSON for an approval request."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":warning: *Approval Required*\n"
                    f"*Task:* {task.description[:120]}\n"
                    f"*Step:* `{subtask.agent_type.value.upper()}` — {subtask.description[:200]}"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                    "style": "primary",
                    "action_id": "approve_action",
                    "value": subtask.id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                    "style": "danger",
                    "action_id": "reject_action",
                    "value": subtask.id,
                },
            ],
        },
    ]


def build_ack_message(task: Task) -> str:
    return (
        f":robot_face: Got it! Starting task:\n> {task.description}\n\n"
        f"I'll keep you updated in this thread. Task ID: `{task.id[:8]}`"
    )


def build_error_message(error: str) -> str:
    return f":x: An error occurred:\n```{error}```"
