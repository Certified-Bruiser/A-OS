import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from app.memory.long_term import LongTermMemory
from app.memory.service import MemoryService


ENABLED = {
    "memoryType": "long-term",
    "persistentMemory": True,
    "userMemory": True,
    "retentionDays": 0,
}


def make_store(tmp_path):
    return LongTermMemory(tmp_path / "durable_memory.json")


def make_service(tmp_path, configuration=None):
    return MemoryService(
        configuration=configuration or ENABLED,
        storage_file=tmp_path / "durable_memory.json",
        archive_storage=tmp_path / "conversations",
    )


def seed(store, agent_id, user_id, value):
    return store.remember(
        agent_id,
        user_id,
        "context",
        "project",
        value,
    )


def start(service, agent_id="agent-a", user_id="user-1"):
    service.start_session(agent_id=agent_id, user_id=user_id)


def test_session_start_loads_exact_scope_into_ram(tmp_path):
    store = make_store(tmp_path)
    expected = seed(store, "agent-a", "user-1", "owned")
    seed(store, "agent-a", "user-2", "other user")
    seed(store, "agent-b", "user-1", "other agent")

    service = make_service(tmp_path)
    start(service)

    assert [memory.id for memory in service.durable_memories] == [expected.id]
    assert [memory.id for memory in service.memories()] == [expected.id]


def test_disabled_settings_do_not_load_durable_memory(tmp_path):
    seed(make_store(tmp_path), "agent-a", "user-1", "persisted")

    for configuration in (
        {**ENABLED, "memoryType": "none"},
        {**ENABLED, "memoryType": "short-term"},
        {**ENABLED, "persistentMemory": False},
        {**ENABLED, "userMemory": False},
    ):
        service = make_service(tmp_path, configuration)
        loader = Mock(wraps=service.long_term.load_active)
        service.long_term.load_active = loader

        start(service)

        assert service.durable_memories == []
        loader.assert_not_called()


def test_retention_is_applied_before_memories_enter_ram(tmp_path):
    store = make_store(tmp_path)
    recent = seed(store, "agent-a", "user-1", "recent")
    expired = seed(store, "agent-a", "user-1", "expired")
    path = tmp_path / "durable_memory.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    old_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    for record in data["memories"]:
        if record["id"] == expired.id:
            record["created_at"] = old_time
    path.write_text(json.dumps(data), encoding="utf-8")

    service = make_service(tmp_path, {**ENABLED, "retentionDays": 1})
    start(service)

    assert [memory.id for memory in service.durable_memories] == [recent.id]


def test_startup_loads_once_and_memories_are_ram_only(tmp_path):
    seed(make_store(tmp_path), "agent-a", "user-1", "persisted")
    service = make_service(tmp_path)
    loader = Mock(wraps=service.long_term.load_active)
    service.long_term.load_active = loader

    start(service)
    assert loader.call_count == 1

    service.memories()
    service.memories()
    service.memories()

    assert loader.call_count == 1


def test_async_startup_offloads_the_one_time_load(tmp_path):
    seed(make_store(tmp_path), "agent-a", "user-1", "persisted")
    service = make_service(tmp_path)
    loader = Mock(wraps=service.long_term.load_active)
    service.long_term.load_active = loader

    asyncio.run(service.start_session_async("agent-a", "user-1"))

    assert len(service.durable_memories) == 1
    assert loader.call_count == 1


def test_end_session_releases_loaded_memory_without_affecting_archive(tmp_path):
    service = make_service(tmp_path)
    start(service)
    service.save_message("user", "working message")
    service.end_session()

    assert service.durable_memories == []
    assert service.get_context() == ""
    assert len(service.sessions()) == 1


def test_fresh_service_reloads_memory_after_session_restart(tmp_path):
    seed(make_store(tmp_path), "agent-a", "user-1", "persisted")
    first = make_service(tmp_path)
    start(first)
    first.end_session()

    second = make_service(tmp_path)
    start(second)

    assert len(second.durable_memories) == 1