import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.memory.model import DurableMemory


class LongTermMemory:

    def __init__(self, file=None):
        self.file = Path(file or "app/memory/storage/durable_memory.json")

        self.file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

    @staticmethod
    def _validate_scope(agent_id, user_id):
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("agent_id is required")
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id is required")

    def _load(self):
        if not self.file.exists():
            return {"memories": []}

        with open(
            self.file,
            "r",
            encoding="utf-8",
        ) as f:

            data = json.load(f)

        return data

    def _save(self, data):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.file.parent,
                prefix=f"{self.file.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(data, temporary_file, indent=4, ensure_ascii=False)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.file)
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _retention_cutoff(retention_days):
        if retention_days in (0, "0", None):
            return None
        try:
            retention_days = int(retention_days)
        except (TypeError, ValueError) as exc:
            raise ValueError("retentionDays must be 0 or a positive number") from exc
        if retention_days < 0:
            raise ValueError("retentionDays must be 0 or a positive number")

        return datetime.now(timezone.utc) - timedelta(days=retention_days)

    def _expire_data(self, data, retention_days):
        cutoff = self._retention_cutoff(retention_days)
        if cutoff is None:
            return False

        changed = False
        for record in data["memories"]:
            if record["status"] != "active":
                continue
            created_at = datetime.fromisoformat(record["created_at"])
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at < cutoff:
                record["status"] = "forgotten"
                record["updated_at"] = datetime.now(timezone.utc).isoformat()
                changed = True
        return changed

    def expire(self, retention_days):
        data = self._load()
        changed = self._expire_data(data, retention_days)
        if changed:
            self._save(data)
        return changed

    def load_active(self, agent_id, user_id, retention_days=0):
        self._validate_scope(agent_id, user_id)
        data = self._load()
        changed = self._expire_data(data, retention_days)
        if changed:
            self._save(data)

        return [
            DurableMemory.from_dict(record)
            for record in data["memories"]
            if record["agent_id"] == agent_id
            and record["user_id"] == user_id
            and record["status"] == "active"
        ]

    def remember(
        self,
        agent_id,
        user_id,
        category,
        key,
        value,
        source="user",
        confidence=1.0,
    ):

        self._validate_scope(agent_id, user_id)
        data = self._load()
        candidate = DurableMemory(
            agent_id=agent_id,
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            source=source,
            confidence=confidence,
        )

        for record in data["memories"]:
            if (
                record["status"] == "active"
                and record["agent_id"] == agent_id
                and record["user_id"] == user_id
                and record["category"] == category
                and record["key"] == key
                and record["value"] == value
            ):
                return DurableMemory.from_dict(record)

        data["memories"].append(candidate.to_dict())
        self._save(data)
        return candidate

    def update(self, memory_id, agent_id, user_id, **changes):
        self._validate_scope(agent_id, user_id)
        data = self._load()
        for index, record in enumerate(data["memories"]):
            if record["id"] != memory_id or record["status"] != "active":
                continue
            if record["agent_id"] != agent_id or record["user_id"] != user_id:
                return None

            updated = dict(record)
            updated.update(changes)
            updated["id"] = record["id"]
            updated["agent_id"] = record["agent_id"]
            updated["user_id"] = record["user_id"]
            updated["created_at"] = record["created_at"]
            updated["status"] = "active"
            updated["updated_at"] = ""
            memory = DurableMemory.from_dict(updated)
            data["memories"][index] = memory.to_dict()
            self._save(data)
            return memory
        return None

    def replace(
        self,
        agent_id,
        user_id,
        category,
        key,
        value,
        source="user",
        confidence=1.0,
    ):
        self._validate_scope(agent_id, user_id)
        data = self._load()
        for record in data["memories"]:
            if (
                record["status"] == "active"
                and record["agent_id"] == agent_id
                and record["user_id"] == user_id
                and record["category"] == category
                and record["key"] == key
            ):
                record["status"] = "superseded"
                record["updated_at"] = ""
                record["updated_at"] = DurableMemory.from_dict(record).updated_at
                break

        replacement = DurableMemory(
            agent_id=agent_id,
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            source=source,
            confidence=confidence,
        )
        data["memories"].append(replacement.to_dict())
        self._save(data)
        return replacement

    def forget(self, memory_id, agent_id, user_id):
        self._validate_scope(agent_id, user_id)
        data = self._load()
        for index, record in enumerate(data["memories"]):
            if record["id"] != memory_id or record["status"] != "active":
                continue
            if record["agent_id"] != agent_id or record["user_id"] != user_id:
                return None
            record["status"] = "forgotten"
            record["updated_at"] = ""
            memory = DurableMemory.from_dict(record)
            data["memories"][index] = memory.to_dict()
            self._save(data)
            return memory
        return None

    def list(self, agent_id, user_id, status="active"):
        self._validate_scope(agent_id, user_id)
        if status not in {None, "active", "superseded", "forgotten"}:
            raise ValueError(f"invalid memory status: {status}")
        return [
            DurableMemory.from_dict(record)
            for record in self._load()["memories"]
            if record["agent_id"] == agent_id
            and record["user_id"] == user_id
            and (status is None or record["status"] == status)
        ]

    def all(self, agent_id, user_id):
        return self.list(agent_id, user_id)
