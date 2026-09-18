from app.memory.model import DurableMemory
from app.memory.service import MAX_RELEVANT_MEMORIES, MemoryService


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


def make_memory(agent_id, user_id, category, key, value, confidence=0.5, status="active"):
    return DurableMemory(
        agent_id=agent_id,
        user_id=user_id,
        category=category,
        key=key,
        value=value,
        confidence=confidence,
        status=status,
    )


def start(service, agent_id="agent-a", user_id="user-a"):
    service.start_session(agent_id, user_id)


def test_no_memories_or_irrelevant_memories_leave_context_empty(tmp_path):
    service = make_service(tmp_path)
    start(service)

    assert service.get_relevant_memory_context("What is the weather?") == ""

    service.durable_memories.append(
        make_memory("agent-a", "user-a", "context", "primary_project", "AgentOS")
    )
    assert service.get_relevant_memory_context("What is the weather?") == ""


def test_relevant_memory_is_compact_and_preserves_precedence_boundary(tmp_path):
    service = make_service(tmp_path)
    start(service)
    memory = make_memory(
        "agent-a", "user-a", "preference", "response_style", "concise answers"
    )
    service.durable_memories.append(memory)

    block = service.get_relevant_memory_context("Tell me about response style")

    assert "Relevant user memory:" in block
    assert "- response_style: concise answers" in block
    assert "current user's statements take precedence" in block
    assert memory.last_used_at is None


def test_selection_is_capped_and_ranked_deterministically(tmp_path):
    service = make_service(tmp_path)
    start(service)
    memories = [
        make_memory("agent-a", "user-a", "context", f"project_{index}", "AgentOS", confidence=index / 10)
        for index in range(5)
    ]
    service.durable_memories.extend(memories)

    block = service.get_relevant_memory_context("project AgentOS")

    assert MAX_RELEVANT_MEMORIES == 3
    assert block.count("- project_") == 3
    assert "- project_4: AgentOS" in block
    assert "- project_3: AgentOS" in block
    assert "- project_2: AgentOS" in block
    assert "- project_1: AgentOS" not in block


def test_scope_and_status_are_enforced_from_ram_collection(tmp_path):
    service = make_service(tmp_path)
    start(service, "agent-a", "user-a")
    service.durable_memories.extend([
        make_memory("agent-a", "user-b", "context", "project", "AgentOS"),
        make_memory("agent-b", "user-a", "context", "project", "AgentOS"),
        make_memory("agent-a", "user-a", "context", "old_project", "AgentOS", status="forgotten"),
        make_memory("agent-a", "user-a", "context", "current_project", "AgentOS"),
    ])

    block = service.get_relevant_memory_context("AgentOS project")

    assert "current_project" in block
    assert "old_project" not in block
    assert "user-b" not in block
    assert "agent-b" not in block


def test_disabled_policy_returns_without_storage_access(tmp_path):
    service = make_service(tmp_path, {**ENABLED, "userMemory": False})
    start(service)
    service.long_term._load = lambda: (_ for _ in ()).throw(AssertionError("disk access"))

    assert service.get_relevant_memory_context("AgentOS project") == ""


def test_selection_does_not_call_storage_or_structured_llm(tmp_path):
    service = make_service(tmp_path)
    start(service)
    service.durable_memories.append(
        make_memory("agent-a", "user-a", "context", "project", "AgentOS")
    )
    service.long_term.list = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("storage access"))

    assert service.get_relevant_memory_context("AgentOS project")