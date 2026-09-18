import asyncio
from types import SimpleNamespace

from app.agent_runtime import AgentOSRuntime
from app.memory.service import MemoryService


class FakeSTT:
    def __init__(self, transcripts):
        self.transcripts = iter(transcripts)
        self.on_speech_start = None
        self.on_speech_end = None

    async def prepare_for_turn(self):
        pass

    async def wait_for_transcript(self, timeout=15):
        return next(self.transcripts)


class FakeLLM:
    def __init__(self):
        self.calls = []
        self.turn = 0
        self.turn_responses = [
            "Good morning! How can I help?",
            "The weather is sunny.",
        ]

    async def stream(self, prompt, context):
        self.calls.append((prompt, context))
        for token in (self.turn_responses[self.turn],):
            yield token
        self.turn += 1


class FakeTTS:
    async def speak(self, response, **kwargs):
        pass


class FakeAudio:
    def begin_playback(self):
        pass

    def play_frame(self, frame):
        pass


class FakeManager:
    def __init__(self):
        self.runtime = None

    async def broadcast(self, event, data):
        if event == "tts_complete":
            self.runtime.playback_complete_event.set()


async def noop_state(state):
    pass


def test_current_transcript_is_prompt_only_and_history_is_preserved(tmp_path):
    memory = MemoryService(
        configuration={"memoryType": "none"},
        storage_file=tmp_path / "durable_memory.json",
        archive_storage=tmp_path / "conversations",
    )
    stt = FakeSTT(["Good morning", "What is the weather?"])
    llm = FakeLLM()
    manager = FakeManager()
    runtime = AgentOSRuntime(
        audio_engine=FakeAudio(),
        stt=stt,
        llm=llm,
        tts=FakeTTS(),
        memory=memory,
        manager=manager,
        set_state=noop_state,
    )
    manager.runtime = runtime
    runtime.agent = SimpleNamespace(id="agent-a")
    runtime.user_id = "user-a"
    runtime.running = True
    memory.start_session("agent-a", "user-a", {"memoryType": "none"})

    asyncio.run(runtime.listen_once())
    asyncio.run(runtime.listen_once())

    first_prompt, first_context = llm.calls[0]
    second_prompt, second_context = llm.calls[1]

    assert first_prompt == "Good morning"
    assert first_context == ""
    assert second_prompt == "What is the weather?"
    assert "user: Good morning\n" in second_context
    assert "assistant: Good morning! How can I help?\n" in second_context
    assert "What is the weather?" not in second_context
    assert second_context.count("Good morning! How can I help?") == 1