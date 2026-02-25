from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentResult:
    success: bool
    output: str = ""
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, output: str = "", **metadata) -> "AgentResult":
        return cls(success=True, output=output, metadata=metadata)

    @classmethod
    def fail(cls, error: str, output: str = "") -> "AgentResult":
        return cls(success=False, output=output, error=error)
