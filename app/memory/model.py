import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


MEMORY_CATEGORIES = {
    "identity",
    "preference",
    "goal",
    "project",
    "context",
}
MEMORY_SOURCES = {"user", "conversation", "system"}
MEMORY_STATUSES = {"active", "superseded", "forgotten"}


@dataclass
class DurableMemory:
    agent_id: str
    user_id: str
    category: str
    key: str
    value: Any
    source: str = "user"
    confidence: float = 1.0
    status: str = "active"
    id: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_used_at: str | None = None

    def __post_init__(self):
        for field_name in ("agent_id", "user_id", "category", "key"):
            field_value = getattr(self, field_name)
            if not isinstance(field_value, str) or not field_value.strip():
                raise ValueError(f"{field_name} is required")

        if self.category not in MEMORY_CATEGORIES:
            raise ValueError(f"invalid memory category: {self.category}")
        if self.source not in MEMORY_SOURCES:
            raise ValueError(f"invalid memory source: {self.source}")
        if self.status not in MEMORY_STATUSES:
            raise ValueError(f"invalid memory status: {self.status}")
        if not isinstance(self.confidence, (int, float)) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        try:
            json.dumps(self.value)
        except (TypeError, ValueError) as exc:
            raise ValueError("value must be JSON-compatible") from exc

        now = datetime.now(timezone.utc).isoformat()
        if not self.id:
            self.id = str(uuid4())
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)