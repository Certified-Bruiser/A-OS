import asyncio
import time

from app.conversation.state import AssistantState


class AgentOSRuntime:

    def __init__(
        self,
        audio_engine,
        stt,
        llm,
        tts,
        memory,
        manager,
        set_state,
    ):

        self.audio_engine = audio_engine
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.memory = memory
        self.manager = manager
        self.set_state = set_state
        self.agent = None

        # --------------------------------------------------
        # Runtime state
        # --------------------------------------------------

        self.interrupted = False
        self.running = False
        self.task = None

        # True only while the assistant is actively generating
        # or speaking a response.
        self.assistant_active = False

        # Prevent multiple simultaneous interrupt operations.
        self.interrupt_lock = asyncio.Lock()

        # Task used to interrupt TTS without blocking the
        # Sarvam STT message listener.
        self.interrupt_task = None

        # --------------------------------------------------
        # Connect STT callbacks
        # --------------------------------------------------

        self.stt.on_speech_start = (
            self.handle_speech_start
        )

        self.stt.on_speech_end = (
            self.handle_speech_end
        )

    def configure(self, agent, stt, llm, tts):
        if self.running:
            raise RuntimeError("Cannot configure a running runtime")

        self.agent = agent
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.stt.on_speech_start = self.handle_speech_start
        self.stt.on_speech_end = self.handle_speech_end

    # ======================================================
    # START
    # ======================================================

    async def start(self):

        if self.running:
            return

        try:

            # --------------------------------------------------
            # Start audio engine / playback worker.
            # --------------------------------------------------

            await self.audio_engine.start()

            # --------------------------------------------------
            # Start memory session.
            # --------------------------------------------------

            self.memory.start_session(
                agent_id=self.agent.id if self.agent else None
            )

            # --------------------------------------------------
            # Connect STT BEFORE microphone capture.
            # --------------------------------------------------

            await self.stt.connect()

            # --------------------------------------------------
            # Connect TTS.
            # --------------------------------------------------

            await self.tts.connect()

            # --------------------------------------------------
            # Mark runtime running BEFORE microphone capture.
            #
            # This is important.
            #
            # STT can produce START_SPEECH as soon as audio
            # starts arriving.
            # --------------------------------------------------

            self.running = True

            # --------------------------------------------------
            # Start continuous microphone capture.
            #
            # AudioEngine should:
            #
            # microphone
            #     ↓
            # AEC / processor
            #     ↓
            # stt.feed_audio(clean_pcm)
            #
            # continuously.
            # --------------------------------------------------

            await self.audio_engine.start_capture(
                self.stt.feed_audio
            )

        except Exception:

            await self._cleanup_on_start_failure()

            raise

        # --------------------------------------------------
        # Start conversation loop.
        # --------------------------------------------------

        self.task = asyncio.create_task(
            self.run()
        )

        print(
            "\n🟢 AgentOS Runtime started"
        )

    # ======================================================
    # STT SPEECH START
    #
    # THIS IS THE BARGE-IN TRIGGER.
    #
    # Sarvam hears the user while TTS is playing.
    # START_SPEECH arrives.
    #
    # We immediately:
    #
    # 1. stop local playback
    # 2. close TTS websocket
    # 3. discard future TTS chunks
    #
    # STT itself stays connected.
    # ======================================================

    async def handle_speech_start(self):

        print(
            "\n🗣️ BARGE-IN: USER SPEECH DETECTED"
        )

        if not self.running:
            return

        # --------------------------------------------------
        # If assistant isn't speaking/generating, this is
        # simply the beginning of a normal user turn.
        # --------------------------------------------------

        if not self.assistant_active:

            print(
                "ℹ️ User speech started normally"
            )

            return

        async with self.interrupt_lock:

            # Another callback may already have interrupted.
            if self.interrupted:
                return

            print(
                "🛑 BARGE-IN: interrupting assistant"
            )

            self.interrupted = True

            # --------------------------------------------------
            # 1. STOP LOCAL PLAYBACK IMMEDIATELY
            # --------------------------------------------------

            try:

                self.audio_engine.stop()

            except Exception as e:

                print(
                    f"⚠️ Audio stop error: {e}"
                )

            # --------------------------------------------------
            # 2. CLOSE TTS SOCKET
            #
            # Don't let this block the STT listener itself.
            # --------------------------------------------------

            try:

                if self.interrupt_task is not None:

                    if not self.interrupt_task.done():

                        self.interrupt_task.cancel()

                self.interrupt_task = asyncio.create_task(
                    self._interrupt_tts()
                )

            except Exception as e:

                print(
                    f"⚠️ TTS interrupt scheduling "
                    f"error: {e}"
                )

            print(
                "✅ BARGE-IN LOCAL STOP COMPLETE"
            )

    # ======================================================
    # TTS INTERRUPT
    # ======================================================

    async def _interrupt_tts(self):

        try:

            await self.tts.interrupt()

            print(
                "🔌 TTS interrupted / websocket closed"
            )

        except asyncio.CancelledError:

            raise

        except Exception as e:

            print(
                f"⚠️ TTS interrupt error: {e}"
            )

    # ======================================================
    # STT SPEECH END
    # ======================================================

    async def handle_speech_end(self):

        print(
            "\n🛑 Sarvam detected end of user speech"
        )

    # ======================================================
    # START FAILURE CLEANUP
    # ======================================================

    async def _cleanup_on_start_failure(self):

        self.running = False
        self.interrupted = False
        self.assistant_active = False

        try:

            await self.audio_engine.stop_capture()

        except Exception:

            pass

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

        if (
            hasattr(self.memory, "session")
            and getattr(
                self.memory.session,
                "active",
                lambda: False,
            )()
        ):

            self.memory.end_session()

    # ======================================================
    # STOP
    # ======================================================

    async def stop(self):

        self.running = False

        self.assistant_active = False
        self.interrupted = True

        # --------------------------------------------------
        # Stop main runtime loop.
        # --------------------------------------------------

        if self.task:

            self.task.cancel()

            try:

                await self.task

            except asyncio.CancelledError:

                pass

            self.task = None

        # --------------------------------------------------
        # Stop any pending TTS interrupt task.
        # --------------------------------------------------

        if self.interrupt_task:

            if not self.interrupt_task.done():

                self.interrupt_task.cancel()

                try:

                    await self.interrupt_task

                except asyncio.CancelledError:

                    pass

            self.interrupt_task = None

        # --------------------------------------------------
        # Stop microphone capture.
        # --------------------------------------------------

        try:

            await self.audio_engine.stop_capture()

        except Exception:

            pass

        # --------------------------------------------------
        # Stop playback.
        # --------------------------------------------------

        try:

            self.audio_engine.stop()

        except Exception:

            pass

        # --------------------------------------------------
        # Disconnect STT.
        # --------------------------------------------------

        try:

            await self.stt.disconnect()

        except Exception:

            pass

        # --------------------------------------------------
        # Disconnect TTS.
        # --------------------------------------------------

        try:

            await self.tts.disconnect()

        except Exception:

            pass

        # --------------------------------------------------
        # End memory session.
        # --------------------------------------------------

        if (
            hasattr(self.memory, "session")
            and getattr(
                self.memory.session,
                "active",
                lambda: False,
            )()
        ):

            self.memory.end_session()

        await self.set_state(
            AssistantState.IDLE
        )

        print(
            "\n🔴 AgentOS Runtime stopped"
        )

    # ======================================================
    # LEGACY INTERRUPT
    # ======================================================

    async def interrupt(self):

        await self.handle_speech_start()

    # ======================================================
    # MAIN LOOP
    # ======================================================

    async def run(self):

        try:

            while self.running:

                await self.listen_once()

        except asyncio.CancelledError:

            print(
                "🛑 Runtime task cancelled"
            )

            raise

        except Exception as e:

            print(
                f"❌ Runtime error: {e}"
            )

    # ======================================================
    # ONE CONVERSATION TURN
    # ======================================================

    async def listen_once(self):

        # --------------------------------------------------
        # New user turn starts here.
        # --------------------------------------------------

        self.interrupted = False
        self.assistant_active = False

        # --------------------------------------------------
        # Tell STT to discard any transcript left over from
        # the previous turn.
        #
        # This is VERY important after barge-in.
        # --------------------------------------------------

        try:

            await self.stt.prepare_for_turn()

        except AttributeError:

            # Compatibility with older STT provider.
            pass

        # --------------------------------------------------
        # LISTENING
        # --------------------------------------------------

        await self.set_state(
            AssistantState.LISTENING
        )

        print(
            "\n🎤 Waiting for user speech..."
        )

        # --------------------------------------------------
        # Sarvam STT is already receiving microphone audio.
        #
        # We do NOT call audio_engine.listen().
        #
        # We simply wait for Sarvam's finalized transcript.
        # --------------------------------------------------

        transcript = await self.stt.wait_for_transcript(
            timeout=15
        )

        if not transcript:

            print(
                "⚠️ No transcript received"
            )

            return

        # --------------------------------------------------
        # If shutdown/interruption happened while waiting,
        # don't process the transcript.
        # --------------------------------------------------

        if not self.running:

            return

        # --------------------------------------------------
        # TRANSCRIPT
        # --------------------------------------------------

        print(
            f"\n👤 User: {transcript}"
        )
        print(f"[AUDIO] transcript received: {transcript}")
        print(
            f"[AUDIO] agent_id={self.agent.id if self.agent else None} "
            f"llm_provider={getattr(self.llm, 'id', 'unknown')} "
            f"llm_model={getattr(getattr(self.llm, 'service', None), 'agent_configuration', {}).get('llmModel', 'sonar')}"
        )

        await self.manager.broadcast(
            "transcript",
            {
                "text": transcript
            }
        )

        self.memory.save_message(
            "user",
            transcript
        )

        # --------------------------------------------------
        # THINKING
        # --------------------------------------------------

        await self.set_state(
            AssistantState.THINKING
        )

        context = self.memory.get_context()

        response_parts = []

        self.assistant_active = True

        try:

            async for token in self.llm.stream(
                transcript,
                context
            ):

                if self.interrupted:

                    print(
                        "🛑 LLM generation interrupted"
                    )

                    return

                response_parts.append(
                    token
                )

        finally:

            # Keep assistant_active true until TTS has
            # completely finished or been interrupted.
            pass

        response = "".join(
            response_parts
        ).strip()
        print("[LLM] response received")

        # --------------------------------------------------
        # Don't speak if user interrupted during LLM.
        # --------------------------------------------------

        if self.interrupted:

            print(
                "🛑 Response discarded after interruption"
            )

            return

        if not response:

            print(
                "⚠️ Empty assistant response"
            )

            return

        # --------------------------------------------------
        # Broadcast response.
        # --------------------------------------------------

        await self.manager.broadcast(
            "assistant",
            {
                "text": response
            }
        )

        # --------------------------------------------------
        # SPEAKING
        # --------------------------------------------------

        await self.set_state(
            AssistantState.SPEAKING
        )

        tts_start = time.perf_counter()

        print(
            "\n🔊 Assistant speaking..."
        )
        print("[AUDIO] sending response to TTS")

        try:
            self.audio_engine.begin_playback()

            await self.tts.speak(
                response,
                on_audio_chunk=self.audio_engine.play_frame,
                tts_start=tts_start,
                should_stop=lambda:
                    self.interrupted,
            )

        except asyncio.CancelledError:

            print(
                "🛑 TTS task cancelled"
            )

            return

        finally:

            self.assistant_active = False

        # --------------------------------------------------
        # BARGE-IN
        # --------------------------------------------------

        if self.interrupted:

            print(
                "\n🛑 Assistant reply interrupted"
            )

            # IMPORTANT:
            #
            # Do NOT save the assistant response as a completed
            # conversational turn.
            #
            # The user interrupted it.
            #

            await self.set_state(
                AssistantState.LISTENING
            )

            # The SAME continuous Sarvam STT connection is
            # already receiving the user's speech.
            #
            # The next loop iteration will consume its
            # finalized transcript.
            #

            return

        # --------------------------------------------------
        # NORMAL COMPLETION
        # --------------------------------------------------

        self.memory.save_message(
            "assistant",
            response
        )

        await self.set_state(
            AssistantState.LISTENING
        )

        print(
            "\n🎤 Assistant finished. "
            "Waiting for next user turn..."
        )


