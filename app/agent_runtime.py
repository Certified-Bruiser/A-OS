import asyncio
import time
from app.conversation.state import AssistantState


class AgentOSRuntime:
    def __init__(self, audio_engine, stt, llm, tts, memory, manager, set_state):
        self.audio_engine = audio_engine
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.memory = memory
        self.manager = manager
        self.set_state = set_state

        self.interrupted = False
        self.running = False
        self.task = None
        self.pending_audio = None

    async def start(self):
        if self.running:
            return

        try:
            await self.audio_engine.start()
            self.memory.start_session()

            # Connect STT websocket
            await self.stt.connect()
            await self.tts.connect()
        except Exception:
            await self._cleanup_on_start_failure()
            raise

        self.running = True
        self.task = asyncio.create_task(self.run())

    async def _cleanup_on_start_failure(self):
        self.running = False
        self.interrupted = False

        try:
            self.audio_engine.stop()
        except Exception:
            pass

        try:
            await self.stt.disconnect()
        except Exception:
            pass

        try:
            await self.tts.disconnect()
        except Exception:
            pass

        if hasattr(self.memory, "session") and getattr(self.memory.session, "active", lambda: False)():
            self.memory.end_session()

    async def stop(self):
        self.running = False

        if self.task:
            self.task.cancel()

            try:
                await self.task
            except asyncio.CancelledError:
                pass

        # Disconnect STT websocket
        try:
            await self.stt.disconnect()
        except Exception:
            pass

        try:
            await self.tts.disconnect()
        except Exception:
            pass

        if hasattr(self.memory, "session") and getattr(self.memory.session, "active", lambda: False)():
            self.memory.end_session()

        # Return UI to idle
        await self.set_state(AssistantState.IDLE)

    async def interrupt(self):
        """
        Interrupt the current conversation pipeline.
        """

        self.interrupted = True

        # Stop any audio currently playing
        self.audio_engine.stop()

        print("🛑 Conversation interrupted")

    async def run(self):
        try:
            while self.running:
                await self.listen_once()

        except asyncio.CancelledError:
            print("Runtime task cancelled")
            raise

        except Exception as e:
            print(f"Runtime error: {e}")

    async def _speak_with_barge_in(self, response, tts_start):
        speaking_task = asyncio.create_task(
            self.tts.speak(
                response,
                on_audio_chunk=self.audio_engine.play_frame,
                tts_start=tts_start,
                should_stop=lambda: self.interrupted,
            )
        )
        listening_task = asyncio.create_task(self.audio_engine.listen())

        try:
            done, _ = await asyncio.wait(
                {speaking_task, listening_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if listening_task in done:
                audio = await listening_task
                self.interrupted = True
                self.audio_engine.stop()
                speaking_task.cancel()

                try:
                    await speaking_task
                except asyncio.CancelledError:
                    pass

                return audio

            await speaking_task
            return None

        finally:
            if not listening_task.done():
                listening_task.cancel()

                try:
                    await listening_task
                except asyncio.CancelledError:
                    pass

            if not speaking_task.done():
                speaking_task.cancel()

                try:
                    await speaking_task
                except asyncio.CancelledError:
                    pass

    async def listen_once(self):
        # Reset interruption flag for new conversation
        self.interrupted = False

        # -----------------------------
        # Listening
        # -----------------------------
        await self.set_state(AssistantState.LISTENING)

        if self.pending_audio is not None:
            audio = self.pending_audio
            self.pending_audio = None
        else:
            audio = await self.audio_engine.listen()

        if not audio:
            return

        # -----------------------------
        # STT
        # -----------------------------
        transcript = await self.stt.transcribe(audio["audio"])

        if not transcript:
            return

        await self.manager.broadcast(
            "transcript",
            {"text": transcript}
        )

        # Save user message
        self.memory.save_message("user", transcript)

        # -----------------------------
        # Thinking
        # -----------------------------
        await self.set_state(AssistantState.THINKING)

        context = self.memory.get_context()

        response_parts = []

        async for token in self.llm.stream(transcript, context):

            if self.interrupted:
                print("🛑 LLM generation interrupted")
                break

            response_parts.append(token)


        response = "".join(response_parts).strip()

        if self.interrupted:
            return

        if not response:
            return

        # Save assistant message
        self.memory.save_message("assistant", response)

        await self.manager.broadcast(
            "assistant",
            {"text": response}
        )

        # -----------------------------
        # Speaking
        # -----------------------------
        await self.set_state(AssistantState.SPEAKING)

        tts_start = time.perf_counter()

        interrupted_audio = await self._speak_with_barge_in(response, tts_start)

        if interrupted_audio is not None:
            self.pending_audio = interrupted_audio
            await self.set_state(AssistantState.INTERRUPTED)
            return

        # After speaking, return to listening
        await self.set_state(AssistantState.LISTENING)

