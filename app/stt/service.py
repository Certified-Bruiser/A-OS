import io
import wave
import base64
import asyncio
import os
import time

from dotenv import load_dotenv
from sarvamai import AsyncSarvamAI

from app.core.state_manager import StateManager


load_dotenv()


class STTService:

    def __init__(self):

        self.state_manager = StateManager()

        self.client = AsyncSarvamAI(
            api_subscription_key=os.getenv(
                "SARVAM_API_KEY"
            )
        )

        # --------------------------------------------------
        # WebSocket
        # --------------------------------------------------

        self.ws = None
        self.ws_context = None

        self.listener_task = None
        self.sender_task = None

        # --------------------------------------------------
        # Continuous microphone audio
        # --------------------------------------------------

        self.audio_queue = asyncio.Queue(
            maxsize=50
        )

        self.audio_buffer = bytearray()

        # 100 ms @ 16 kHz / mono / 16-bit
        #
        # 16000 samples/sec
        # 100 ms = 1600 samples
        # 1600 * 2 bytes = 3200 bytes
        #
        self.STT_CHUNK_BYTES = 3200

        # --------------------------------------------------
        # Transcript handling
        # --------------------------------------------------

        self.transcript_queue = asyncio.Queue()

        self.transcript = ""

        # --------------------------------------------------
        # Speech events
        # --------------------------------------------------

        self.speech_start_event = asyncio.Event()
        self.speech_end_event = asyncio.Event()

        self.speech_active = False

        # --------------------------------------------------
        # Runtime callbacks
        # --------------------------------------------------

        self.on_speech_start = None
        self.on_speech_end = None

        # --------------------------------------------------
        # Connection state
        # --------------------------------------------------

        self.connected = False
        
        # --------------------------------------------------
        # Latency timing (set by agent runtime)
        # --------------------------------------------------
        
        self.turn_timing = None

    # ======================================================
    # CONNECT
    # ======================================================

    async def connect(self):

        if self.ws is not None:
            return

        print("\n🔌 Connecting to Sarvam STT...")

        self.ws_context = (
            self.client.speech_to_text_streaming.connect(
                model="saaras:v3",
                mode="transcribe",
                language_code="en-IN",

                sample_rate=16000,

                # Important for detecting short barge-ins.
                high_vad_sensitivity=True,

                # We need START_SPEECH / END_SPEECH.
                vad_signals=True,

                # Detect interruption quickly.
                interrupt_min_speech_frames=2,

                # Preserve a little audio before VAD fires.
                pre_speech_pad_frames=9,

                # Don't require a long first utterance.
                first_turn_min_speech_frames=4,

                flush_signal=True,
            )
        )

        self.ws = await self.ws_context.__aenter__()

        self.connected = True

        print("🟢 Connected to Sarvam STT")

        # Start receiver.
        self.listener_task = asyncio.create_task(
            self.process_messages()
        )

        # Start continuous microphone sender.
        self.sender_task = asyncio.create_task(
            self._send_audio_loop()
        )

    # ======================================================
    # PCM -> WAV
    #
    # Sarvam receives WAV chunks over the streaming API.
    # ======================================================

    def _pcm_to_wav(self, pcm: bytes):

        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as wf:

            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)

            wf.writeframes(pcm)

        return buffer.getvalue()

    # ======================================================
    # FEED MICROPHONE AUDIO
    #
    # AudioEngine should continuously call:
    #
    # await stt.feed_audio(clean_frame)
    #
    # IMPORTANT:
    # clean_frame should be the AEC-processed microphone
    # audio, NOT the raw microphone frame.
    # ======================================================

    async def feed_audio(self, pcm: bytes):

        if not pcm:
            return

        if not self.connected:
            return

        try:

            self.audio_queue.put_nowait(pcm)

        except asyncio.QueueFull:

            # Never block microphone capture because STT is slow.
            #
            # Dropping the oldest frame is preferable to
            # accumulating several seconds of latency.
            #
            try:

                old_frame = self.audio_queue.get_nowait()

                self.audio_queue.task_done()

            except asyncio.QueueEmpty:

                pass

            try:

                self.audio_queue.put_nowait(pcm)

            except asyncio.QueueFull:

                pass

    # ======================================================
    # CONTINUOUS AUDIO SENDER
    # ======================================================

    async def _send_audio_loop(self):

        print("🎙️ STT audio sender running")

        try:

            while True:

                pcm = await self.audio_queue.get()

                try:

                    self.audio_buffer.extend(pcm)

                    while (
                        len(self.audio_buffer)
                        >= self.STT_CHUNK_BYTES
                    ):

                        chunk = bytes(
                            self.audio_buffer[
                                :self.STT_CHUNK_BYTES
                            ]
                        )

                        del self.audio_buffer[
                            :self.STT_CHUNK_BYTES
                        ]

                        # ----------------------------------
                        # Convert PCM → WAV
                        # ----------------------------------

                        wav_bytes = self._pcm_to_wav(
                            chunk
                        )

                        encoded = (
                            base64.b64encode(
                                wav_bytes
                            ).decode("utf-8")
                        )

                        # ----------------------------------
                        # Make sure connection still exists
                        # ----------------------------------

                        if self.ws is None:
                            continue

                        # ----------------------------------
                        # Send to Sarvam
                        # ----------------------------------

                        try:

                            await self.ws.transcribe(
                                audio=encoded,
                                encoding="audio/wav",
                                sample_rate=16000,
                            )

                        except asyncio.CancelledError:

                            raise

                        except Exception as e:

                            print(
                                f"\n❌ STT send error: {e}"
                            )

                            # Don't kill the sender task
                            # because one failed frame shouldn't
                            # destroy the entire conversation.

                finally:

                    self.audio_queue.task_done()

        except asyncio.CancelledError:

            print(
                "🛑 STT audio sender cancelled"
            )

            raise

        except Exception as e:

            print(
                f"❌ STT audio sender crashed: {e}"
            )

    # ======================================================
    # WAIT FOR USER TRANSCRIPT
    #
    # This replaces the old:
    #
    #   transcribe(wav_bytes)
    #
    # model.
    #
    # STT is already receiving microphone audio continuously.
    # ======================================================

    async def wait_for_transcript(
        self,
        timeout=10
    ):

        print(
            "\n⏳ Waiting for Sarvam transcript..."
        )

        try:

            transcript = await asyncio.wait_for(
                self.transcript_queue.get(),
                timeout=timeout,
            )

            self.transcript_queue.task_done()

            transcript = (
                transcript or ""
            ).strip()

            if transcript:

                print(
                    f"\n📝 Final transcript: "
                    f"{transcript}"
                )

            return transcript

        except asyncio.TimeoutError:

            print(
                "\n❌ Transcript timeout"
            )

            return ""

    # ======================================================
    # OPTIONAL COMPATIBILITY METHOD
    #
    # If some older code still calls:
    #
    #     await stt.transcribe(wav_bytes)
    #
    # this method can still accept it.
    #
    # New runtime code should use:
    #
    #     await stt.wait_for_transcript()
    #
    # ======================================================

    async def transcribe(
        self,
        wav_bytes: bytes
    ):

        if not wav_bytes:

            return ""

        if self.ws is None:

            print(
                "❌ STT websocket is not connected"
            )

            return ""

        print(
            "\n📤 Sending compatibility audio "
            "to Sarvam STT..."
        )

        try:

            encoded = base64.b64encode(
                wav_bytes
            ).decode("utf-8")

            await self.ws.transcribe(
                audio=encoded,
                encoding="audio/wav",
                sample_rate=16000,
            )

            # Ask Sarvam to finish the current buffered
            # utterance.
            await self.ws.flush()

        except Exception as e:

            print(
                f"❌ STT transcribe error: {e}"
            )

            return ""

        return await self.wait_for_transcript(
            timeout=10
        )

    # ======================================================
    # PREPARE FOR A NEW USER TURN
    #
    # Clears stale transcript state.
    #
    # IMPORTANT:
    # Don't clear the audio queue here because microphone
    # audio should remain continuous.
    # ======================================================

    async def prepare_for_turn(self):

        self.transcript = ""

        self.speech_start_event.clear()
        self.speech_end_event.clear()

        # Remove stale transcripts from previous turns.
        while True:

            try:

                old_transcript = (
                    self.transcript_queue.get_nowait()
                )

                self.transcript_queue.task_done()

                print(
                    f"🧹 Discarding stale transcript: "
                    f"{old_transcript}"
                )

            except asyncio.QueueEmpty:

                break

    # ======================================================
    # WAIT FOR SPEECH START
    # ======================================================

    async def wait_for_speech_start(
        self,
        timeout=None
    ):

        self.speech_start_event.clear()

        try:

            if timeout is None:

                await self.speech_start_event.wait()

            else:

                await asyncio.wait_for(
                    self.speech_start_event.wait(),
                    timeout=timeout,
                )

            return True

        except asyncio.TimeoutError:

            return False

    # ======================================================
    # WAIT FOR SPEECH END
    # ======================================================

    async def wait_for_speech_end(
        self,
        timeout=10
    ):

        try:

            await asyncio.wait_for(
                self.speech_end_event.wait(),
                timeout=timeout,
            )

            return True

        except asyncio.TimeoutError:

            print(
                "\n⚠️ Speech-end timeout"
            )

            return False

    # ======================================================
    # PROCESS SARVAM MESSAGES
    # ======================================================

    async def process_messages(self):

        print(
            "📡 STT message listener running"
        )

        try:

            async for message in self.ws:

                # ==================================================
                # VAD EVENTS
                # ==================================================

                if message.type == "events":

                    signal = (
                        message.data.signal_type
                    )

                    print(
                        f"\n🎙️ Sarvam STT: "
                        f"{signal}"
                    )

                    # ----------------------------------------------
                    # USER STARTED SPEAKING
                    # ----------------------------------------------

                    if signal == "START_SPEECH":

                        if not self.speech_active:

                            self.speech_active = True
                            
                            # Record speech start time for latency
                            if self.turn_timing:
                                self.turn_timing.stt_speech_start = time.perf_counter()

                            self.speech_start_event.set()

                            print(
                                "\n🗣️ USER SPEECH START"
                            )

                            # Runtime uses this as the REAL
                            # barge-in trigger.
                            if self.on_speech_start:

                                try:

                                    result = (
                                        self.on_speech_start()
                                    )

                                    if asyncio.iscoroutine(
                                        result
                                    ):

                                        await result

                                except Exception as e:

                                    print(
                                        "\n❌ Speech-start "
                                        f"callback error: {e}"
                                    )

                    # ----------------------------------------------
                    # USER STOPPED SPEAKING
                    # ----------------------------------------------

                    elif signal == "END_SPEECH":

                        self.speech_active = False

                        self.speech_end_event.set()

                        print(
                            "\n🛑 USER SPEECH END"
                        )

                        if self.on_speech_end:

                            try:

                                result = (
                                    self.on_speech_end()
                                )

                                if asyncio.iscoroutine(
                                    result
                                ):

                                    await result

                            except Exception as e:

                                print(
                                    "\n❌ Speech-end "
                                    f"callback error: {e}"
                                )

                # ==================================================
                # TRANSCRIPT
                # ==================================================

                elif message.type == "data":

                    transcript = (
                        getattr(
                            message.data,
                            "transcript",
                            ""
                        )
                        or ""
                    ).strip()

                    if not transcript:

                        continue

                    print(
                        "\n📝 Transcript: "
                        f"{transcript}"
                    )
                    
                    # Record first result time if this is the first result
                    if (self.turn_timing and 
                        self.turn_timing.stt_first_result is None):
                        self.turn_timing.stt_first_result = time.perf_counter()

                    # Keep the latest transcript for debugging/
                    # compatibility.
                    self.transcript = transcript

                    # Put it into the queue consumed by
                    # wait_for_transcript().
                    await self.transcript_queue.put(
                        transcript
                    )

                # ==================================================
                # UNKNOWN MESSAGE
                # ==================================================

                else:

                    print(
                        f"\n⚠️ Unknown STT message: "
                        f"{message}"
                    )

        except asyncio.CancelledError:

            print(
                "🛑 STT listener cancelled"
            )

            raise

        except Exception as e:

            print(
                f"\n❌ STT listener error: {e}"
            )

    # ======================================================
    # DISCONNECT
    # ======================================================

    async def disconnect(self):

        print(
            "\n🔌 Disconnecting Sarvam STT..."
        )

        self.connected = False

        self.speech_active = False

        self.speech_start_event.clear()
        self.speech_end_event.clear()

        # --------------------------------------------------
        # Stop audio sender
        # --------------------------------------------------

        if self.sender_task:

            self.sender_task.cancel()

            try:

                await self.sender_task

            except asyncio.CancelledError:

                pass

            self.sender_task = None

        # --------------------------------------------------
        # Stop message listener
        # --------------------------------------------------

        if self.listener_task:

            self.listener_task.cancel()

            try:

                await self.listener_task

            except asyncio.CancelledError:

                pass

            self.listener_task = None

        # --------------------------------------------------
        # Close websocket
        # --------------------------------------------------

        if self.ws_context:

            try:

                await self.ws_context.__aexit__(
                    None,
                    None,
                    None,
                )

            except Exception as e:

                print(
                    f"⚠️ STT disconnect error: {e}"
                )

        self.ws_context = None
        self.ws = None

        # --------------------------------------------------
        # Clear local buffers
        # --------------------------------------------------

        self.audio_buffer.clear()

        while True:

            try:

                self.audio_queue.get_nowait()

                self.audio_queue.task_done()

            except asyncio.QueueEmpty:

                break

        while True:

            try:

                self.transcript_queue.get_nowait()

                self.transcript_queue.task_done()

            except asyncio.QueueEmpty:

                break

        print(
            "🔴 Sarvam STT disconnected"
        )


