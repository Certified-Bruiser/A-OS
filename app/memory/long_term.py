import json
from pathlib import Path

from app.memory.model import DurableMemory


class LongTermMemory:

    def __init__(self, file=None):
        self.file = Path(file or "app/memory/storage/durable_memory.json")

        self.file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.file.exists():
            with open(
                self.file,
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    {"memories": []},
                    f,
                    indent=4,
                    ensure_ascii=False,
                )

    def _load(self):

        with open(
            self.file,
            "r",
            encoding="utf-8",
        ) as f:

            return json.load(f)

    def _save(self, data):

        with open(
            self.file,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False,
            )

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
        if not agent_id or not user_id:
            raise ValueError("agent_id and user_id are required")
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

    def clear(self):

        self._save(
            {
                "memories": []
            }
        )
