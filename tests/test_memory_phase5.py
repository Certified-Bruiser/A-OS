import asyncio
import json

from app.agent_runtime import AgentOSRuntime
from app.memory.service import MemoryService


ENABLED = {
    "memoryType": "long-term",
    "persistentMemory": True,
    "userMemory": True,
    "retentionDays": 0,
}


class FakeLLM:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def generate_structured(self, prompt, context, schema):
        self.calls.append((prompt, context, schema))
        return self.result


def make_service(tmp_path, configuration=None):
    return MemoryService(
        configuration=configuration or ENABLED,
        storage_file=tmp_path / "durable_memory.json",
        archive_storage=tmp_path / "conversations",
    )


def candidate(category="preference", key="response_style", value="concise"):
    return json.dumps({
        "memories": [{
            "category": category,
            "key": key,
            "value": value,
            "confidence": 0.9,
        }],
    })


def test_learning_persists_scoped_memory_and_updates_ram(tmp_path):
    service = make_service(tmp_path)
    service.start_session("agent-a", "user-a")
    llm = FakeLLM(candidate())

    operations = asyncio.run(service.learn_from_turn(
        llm,
        "I prefer concise answers.",
        "I will keep answers concise.",
        "agent-a",
        "user-a",
        service.session.session_id,
    ))

    assert operations == 1
    assert len(service.durable_memories) == 1
    assert service.durable_memories[0].source == "conversation"
    assert service.durable_memories[0].agent_id == "agent-a"
    assert service.durable_memories[0].user_id == "user-a"
    assert "I prefer concise answers." in llm.calls[0][1]
    assert "I will keep answers concise." in llm.calls[0][1]


def test_empty_and_malformed_output_do_not_mutate_memory(tmp_path):
    service = make_service(tmp_path)
    service.start_session("agent-a", "user-a")

    for result in ('{"memories": []}', "not json"):
        llm = FakeLLM(result)
        assert asyncio.run(service.learn_from_turn(
            llm, "temporary question", "answer", "agent-a", "user-a",
            service.session.session_id,
        )) == 0

    assert service.durable_memories == []


def test_identical_candidate_is_noop_and_changed_value_replaces(tmp_path):
    service = make_service(tmp_path)
    service.start_session("agent-a", "user-a")
    session_id = service.session.session_id
    first = FakeLLM(candidate(value="AgentOS"))
    changed = FakeLLM(candidate(value="AgentOS Phase 5"))

    asyncio.run(service.learn_from_turn(first, "goal", "reply", "agent-a", "user-a", session_id))
    original_id = service.durable_memories[0].id
    assert asyncio.run(service.learn_from_turn(first, "goal", "reply", "agent-a", "user-a", session_id)) == 0
    assert asyncio.run(service.learn_from_turn(changed, "goal", "reply", "agent-a", "user-a", session_id)) == 1

    assert len(service.durable_memories) == 1
    assert service.durable_memories[0].value == "AgentOS Phase 5"
    assert service.durable_memories[0].id != original_id


def test_disabled_policy_skips_extraction(tmp_path):
    service = make_service(tmp_path, {**ENABLED, "userMemory": False})
    service.start_session("agent-a", "user-a")
    llm = FakeLLM(candidate())

    assert asyncio.run(service.learn_from_turn(
        llm, "durable fact", "reply", "agent-a", "user-a",
        service.session.session_id,
    )) == 0
    assert llm.calls == []


def test_scope_and_session_id_are_captured(tmp_path):
    service = make_service(tmp_path)
    service.start_session("agent-a", "user-a")
    old_session_id = service.session.session_id
    llm = FakeLLM(candidate())

    service.end_session()
    service.start_session("agent-b", "user-b")

    assert asyncio.run(service.learn_from_turn(
        llm, "old fact", "reply", "agent-a", "user-a", old_session_id,
    )) == 1
    assert service.durable_memories == []
    assert len(service.long_term.load_active("agent-a", "user-a", 0)) == 1


def test_persistence_failure_does_not_escape_learning_task(tmp_path):
    service = make_service(tmp_path)
    service.start_session("agent-a", "user-a")
    service.long_term.remember = lambda *args: (_ for _ in ()).throw(OSError("disk"))
    llm = FakeLLM(candidate())

    assert asyncio.run(service.learn_from_turn(
        llm, "durable fact", "reply", "agent-a", "user-a",
        service.session.session_id,
    )) == 0
    assert service.durable_memories == []


def test_concurrent_learning_keeps_both_records(tmp_path):
    service = make_service(tmp_path)
    service.start_session("agent-a", "user-a")
    session_id = service.session.session_id

    async def learn(key, value):
        return await service.learn_from_turn(
            FakeLLM(candidate(key=key, value=value)),
            "durable fact",
            "reply",
            "agent-a",
            "user-a",
            session_id,
        )

    async def scenario():
        return await asyncio.gather(learn("one", "1"), learn("two", "2"))

    assert asyncio.run(scenario()) == [1, 1]
    assert {memory.key for memory in service.durable_memories} == {"one", "two"}


def test_pending_learning_can_be_cancelled_on_shutdown(tmp_path):
    service = make_service(tmp_path)
    service.start_session("agent-a", "user-a")
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocked_extract(prompt, context, schema):
        started.set()
        await release.wait()
        return candidate()

    async def scenario():
        class LLM:
            generate_structured = staticmethod(blocked_extract)

        task = asyncio.create_task(service.learn_from_turn(
            LLM(),
            "fact",
            "reply",
            "agent-a",
            "user-a",
            service.session.session_id,
        ))
        await started.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return task.cancelled()

    assert asyncio.run(scenario())


def test_runtime_stop_does_not_cancel_memory_tasks_when_configured_false(tmp_path):
    service = make_service(tmp_path)
    service.start_session("agent-a", "user-a")

    class FakeAudio:
        async def stop_capture(self):
            return None
        def stop(self):
            return None

    class FakeSTT:
        async def disconnect(self):
            return None
        on_speech_start = None
        on_speech_end = None

    class FakeTTS:
        async def disconnect(self):
            return None

    async def async_set_state(*_):
        return None

    runtime = AgentOSRuntime(
        audio_engine=FakeAudio(),
        stt=FakeSTT(),
        llm=FakeLLM(candidate()),
        tts=FakeTTS(),
        memory=service,
        manager=None,
        set_state=async_set_state,
    )

    async def scenario():
        runtime.running = True
        runtime.task = asyncio.create_task(asyncio.sleep(0))

        started = asyncio.Event()
        release = asyncio.Event()

        async def blocked():
            started.set()
            await release.wait()
            return "done"

        task = asyncio.create_task(blocked())
        runtime.memory_tasks.add(task)

        await started.wait()
        await runtime.stop(cancel_memory_tasks=False)
        assert task.cancelled() is False
        assert task.done() is False
        assert len(runtime.memory_tasks) == 1

        release.set()
        await task
        return True

    assert asyncio.run(scenario()) is True


def test_memory_learning_survives_session_end_and_persists_with_original_scope(tmp_path):
    service = make_service(tmp_path)
    service.start_session("agent-a", "user-a")
    session_id = service.session.session_id
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocked_extract(prompt, context, schema):
        started.set()
        await release.wait()
        return candidate(key="preferred_name", value="Ava")

    class LLM:
        generate_structured = staticmethod(blocked_extract)

    async def scenario():
        task = asyncio.create_task(service.learn_from_turn(
            LLM(),
            "My name is Ava.",
            "Nice to meet you.",
            "agent-a",
            "user-a",
            session_id,
            memory_learning_enabled=True,
        ))
        await started.wait()
        service.end_session()
        service.start_session("agent-b", "user-b")
        release.set()
        result = await task
        assert result == 1
        assert service.durable_memories == []
        reloaded = service.long_term.load_active("agent-a", "user-a", 0)
        assert len(reloaded) == 1
        assert reloaded[0].agent_id == "agent-a"
        assert reloaded[0].user_id == "user-a"

    asyncio.run(scenario())


def test_memory_policy_is_captured_for_already_scheduled_turn(tmp_path):
    service = make_service(tmp_path)
    service.start_session("agent-a", "user-a")
    session_id = service.session.session_id
    service.configuration["userMemory"] = False

    async def scenario():
        task = asyncio.create_task(service.learn_from_turn(
            FakeLLM(candidate(key="favorite_color", value="blue")),
            "I like blue.",
            "That suits you.",
            "agent-a",
            "user-a",
            session_id,
            memory_learning_enabled=True,
        ))
        return await task

    assert asyncio.run(scenario()) == 1
    assert len(service.long_term.load_active("agent-a", "user-a", 0)) == 1
