import json

import pytest

from app.memory.long_term import LongTermMemory
from app.memory.model import DurableMemory


def make_store(tmp_path):
    return LongTermMemory(tmp_path / "durable_memory.json")


def remember(store, agent="agent-a", user="user-a", value="AgentOS"):
    return store.remember(agent, user, "project", "current_project", value)


def test_remember_is_structured_scoped_and_idempotent(tmp_path):
    store = make_store(tmp_path)
    memory = remember(store)
    duplicate = remember(store)

    assert memory.status == "active"
    assert memory.id == duplicate.id
    assert memory.agent_id == "agent-a"
    assert memory.user_id == "user-a"
    assert len(store.list("agent-a", "user-a")) == 1


def test_update_preserves_identity_and_creation_time(tmp_path):
    store = make_store(tmp_path)
    memory = remember(store)
    updated = store.update(memory.id, "agent-a", "user-a", value="AgentOS memory")

    assert updated.id == memory.id
    assert updated.created_at == memory.created_at
    assert updated.updated_at != memory.updated_at
    assert updated.value == "AgentOS memory"


def test_mutations_cannot_cross_ownership_boundaries(tmp_path):
    store = make_store(tmp_path)
    memory = remember(store)

    assert store.update(memory.id, "agent-b", "user-a", value="wrong") is None
    assert store.update(memory.id, "agent-a", "user-b", value="wrong") is None
    assert store.forget(memory.id, "agent-b", "user-a") is None
    assert store.forget(memory.id, "agent-a", "user-b") is None
    assert store.list("agent-a", "user-b") == []
    assert store.list("agent-b", "user-a") == []


def test_replace_supersedes_old_record_and_creates_new_id(tmp_path):
    store = make_store(tmp_path)
    original = remember(store)
    replacement = store.replace(
        "agent-a", "user-a", "project", "current_project", "AgentOS Phase 2"
    )

    assert replacement.id != original.id
    records = store.list("agent-a", "user-a", status=None)
    assert [record.status for record in records] == ["superseded", "active"]
    assert records[0].id == original.id


def test_replace_cannot_supersede_another_owner_memory(tmp_path):
    store = make_store(tmp_path)
    original = remember(store)

    replacement = store.replace(
        "agent-b", "user-a", "project", "current_project", "other project"
    )

    assert replacement.id != original.id
    assert store.list("agent-a", "user-a")[0].id == original.id
    assert store.list("agent-b", "user-a")[0].id == replacement.id


def test_forget_marks_memory_without_deleting_it(tmp_path):
    store = make_store(tmp_path)
    memory = remember(store)
    forgotten = store.forget(memory.id, "agent-a", "user-a")

    assert forgotten.status == "forgotten"
    assert store.list("agent-a", "user-a") == []
    assert store.list("agent-a", "user-a", status="forgotten")[0].id == memory.id


def test_validation_rejects_invalid_fields(tmp_path):
    store = make_store(tmp_path)

    with pytest.raises(ValueError):
        remember(store, value=object())
    with pytest.raises(ValueError):
        store.remember("agent-a", "user-a", "unknown", "key", "value")
    with pytest.raises(ValueError):
        store.remember("agent-a", "user-a", "project", "key", "value", confidence=1.1)
    with pytest.raises(ValueError):
        store.list("agent-a", "user-a", status="unknown")
    with pytest.raises(ValueError):
        DurableMemory(
            agent_id="agent-a",
            user_id="user-a",
            category="project",
            key="key",
            value="value",
            status="unknown",
        )


def test_legacy_global_facts_are_not_imported(tmp_path):
    legacy_file = tmp_path / "long_term.json"
    legacy_file.write_text(json.dumps({"memories": ["global fact"]}), encoding="utf-8")

    store = LongTermMemory(tmp_path / "durable_memory.json")

    assert store.list("agent-a", "user-a") == []
    assert json.loads(legacy_file.read_text(encoding="utf-8"))["memories"] == ["global fact"]