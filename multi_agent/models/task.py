from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class AgentType(Enum):
    CODE = "code"
    FILE = "file"
    GIT = "git"
    TEST = "test"
    ORCHESTRATOR = "orchestrator"


@dataclass
class SubTask:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    agent_type: AgentType = AgentType.CODE
    requires_approval: bool = False
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    slack_channel: str = ""
    slack_thread_ts: str = ""
    slack_user: str = ""
    status: TaskStatus = TaskStatus.PENDING
    subtasks: list[SubTask] = field(default_factory=list)
    current_subtask_index: int = 0
    created_at: Optional[str] = None
    completed_at: Optional[str] = None

    @property
    def progress_pct(self) -> int:
        if not self.subtasks:
            return 0
        done = sum(
            1 for st in self.subtasks
            if st.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.REJECTED)
        )
        return int(done / len(self.subtasks) * 100)

    @property
    def current_subtask(self) -> Optional[SubTask]:
        if self.current_subtask_index < len(self.subtasks):
            return self.subtasks[self.current_subtask_index]
        return None
