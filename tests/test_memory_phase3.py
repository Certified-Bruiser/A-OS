import json
from datetime import datetime, timedelta, timezone

import pytest

from app.memory.service import MemoryService
from app.memory.long_term import LongTermMemory


ENABLED = {
    "memoryType": "long-term",
    "persistentMemory": True,
    "userMemory": True,
    "retentionDays": 0,
}


def make_service(tmp_path, configuration=None):
    return MemoryService(
        configuration=configuration or ENABLED,
        storage_file=tmp_path / "durable_memory.json",
        archive_storage=tmp_path / "conversations",
    )


def start(service, agent_id="agent-a", user_id="user-a", configuration=None):
    service.start_session(
        agent_id=agent_id,
        user_id=user_id,
        configuration=configuration,
    )


def remember(service, value="AgentOS"):
    return service.remember("context", "project", value)


def test_durable_memory_persists_across_service_instances(tmp_path):
    first = make_service(tmp_path)
    start(first)
    created = remember(first)

    second = make_service(tmp_path)
    start(second)

    memories = second.memories()
    assert memories[0].id == created.id
    assert memories[0].agent_id == "agent-a"
    assert memories[0].user_id == "user-a"


@pytest.mark.parametrize(
    "configuration",
    [
        {"memoryType": "none", "persistentMemory": True, "userMemory": True},
        {"memoryType": "short-term", "persistentMemory": True, "userMemory": True},
        {"memoryType": "long-term", "persistentMemory": False, "userMemory": True},
        {"memoryType": "long-term", "persistentMemory": True, "userMemory": False},
    ],
)
def test_durable_memory_requires_all_existing_settings(tmp_path, configuration):
    service = make_service(tmp_path, configuration)
    start(service)

    assert remember(service) is None
    assert service.memories() == []
    assert not (tmp_path / "durable_memory.json").exists()


def test_enabled_settings_persist_durable_memory(tmp_path):
    service = make_service(tmp_path)
    start(service)

    assert remember(service)
    assert (tmp_path / "durable_memory.json").exists()


def test_user_and_agent_scopes_are_completely_isolated(tmp_path):
    service = make_service(tmp_path)

    start(service, "agent-a", "user-1")
    user_one_agent_a = remember(service, "A1")
    start(service, "agent-a", "user-2")
    user_two_agent_a = remember(service, "A2")
    start(service, "agent-b", "user-1")
    user_one_agent_b = remember(service, "B1")
    start(service, "agent-b", "user-2")
    user_two_agent_b = remember(service, "B2")

    scopes = {
        ("agent-a", "user-1"): user_one_agent_a,
        ("agent-a", "user-2"): user_two_agent_a,
        ("agent-b", "user-1"): user_one_agent_b,
        ("agent-b", "user-2"): user_two_agent_b,
    }
    for (agent_id, user_id), expected in scopes.items():
        start(service, agent_id, user_id)
        memories = service.memories()
        assert [memory.id for memory in memories] == [expected.id]


def test_retention_forgets_expired_records_at_storage_access(tmp_path):
    configuration = {**ENABLED, "retentionDays": 1}
    service = make_service(tmp_path, configuration)
    start(service)
    recent = remember(service, "recent")
    expired = remember(service, "expired")

    path = tmp_path / "durable_memory.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    old_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    for record in data["memories"]:
        if record["id"] == expired.id:
            record["created_at"] = old_time
    path.write_text(json.dumps(data), encoding="utf-8")

    storage = LongTermMemory(path)
    storage.expire(configuration["retentionDays"])
    active = storage.list("agent-a", "user-a")
    assert [memory.id for memory in active] == [recent.id]
    all_records = json.loads(path.read_text(encoding="utf-8"))["memories"]
    expired_record = next(record for record in all_records if record["id"] == expired.id)
    assert expired_record["status"] == "forgotten"
    assert expired_record["created_at"] == old_time
    assert expired_record["updated_at"] != ""


def test_forever_retention_preserves_old_records(tmp_path):
    service = make_service(tmp_path, {**ENABLED, "retentionDays": 0})
    start(service)
    memory = remember(service)
    path = tmp_path / "durable_memory.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["memories"][0]["created_at"] = "2000-01-01T00:00:00+00:00"
    path.write_text(json.dumps(data), encoding="utf-8")

    assert service.memories()[0].id == memory.id
    assert service.memories()[0].status == "active"


def test_retention_does_not_change_working_memory_or_archive(tmp_path):
    service = make_service(tmp_path, {**ENABLED, "retentionDays": 1})
    start(service)
    service.save_message("user", "working message")
    before = service.get_context()

    assert service.memories() == []
    assert service.get_context() == before
    assert service.sessions() == []


def test_legacy_storage_is_not_imported(tmp_path):
    legacy_path = tmp_path / "long_term.json"
    legacy_path.write_text(json.dumps({"memories": ["global fact"]}), encoding="utf-8")

    service = make_service(tmp_path)
    start(service)

    assert service.memories() == []
    assert json.loads(legacy_path.read_text(encoding="utf-8"))["memories"] == ["global fact"]