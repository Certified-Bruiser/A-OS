import os
import asyncio
import base64

from dotenv import load_dotenv
from sarvamai import AsyncSarvamAI


load_dotenv()


class SarvamStreamingTTS:

    def __init__(self):

        self.client = AsyncSarvamAI(
            api_subscription_key=os.getenv(
                "SARVAM_API_KEY"
            )
        )

        # --------------------------------------------------
        # WebSocket state
        # --------------------------------------------------

        self.ws = None
        self.ws_context = None

        # --------------------------------------------------
        # Listener
        # --------------------------------------------------

        self.listener_task = None

        # --------------------------------------------------
        # Synchronization
        #
        # IMPORTANT:
        # This was missing in your current version.
        # --------------------------------------------------

        self._connect_lock = asyncio.Lock()

        # --------------------------------------------------
        # Current audio callback
        # --------------------------------------------------

        self.audio_callback = None

        # --------------------------------------------------
        # Current TTS generation
        # --------------------------------------------------

        self.done_event = asyncio.Event()

        # Used to prevent stale audio from a previous
        # generation being played after barge-in.
        self.generation = 0

        # Lock for the current speak operation.
        self.speak_lock = asyncio.Lock()

        print("🟢 SarvamStreamingTTS initialized")

    # ======================================================
    # CONNECT
    # ======================================================

    async def connect(self):

        async with self._connect_lock:

            # Already connected.
            if (
                self.ws is not None
                and self.ws_context is not None
            ):
                return

            print(
                "\n🔌 Connecting Sarvam Streaming TTS..."
            )

            self.ws_context = (
                self.client.text_to_speech_streaming.connect(
                    model="bulbul:v3",
                    send_completion_event=True,
                )
            )

            self.ws = await (
                self.ws_context.__aenter__()
            )

            await self.ws.configure(
                target_language_code="en-IN",
                speaker="rahul",
                output_audio_codec="linear16",
                speech_sample_rate=16000,
            )

            # Start receiver after configuration.
            self.listener_task = asyncio.create_task(
                self.process_messages()
            )

            print(
                "🟢 Connected to Sarvam Streaming TTS"
            )

    # ======================================================
    # INTERNAL DISCONNECT
    # ======================================================

    async def _disconnect_ws(self):

        # --------------------------------------------------
        # Detach listener first.
        # --------------------------------------------------

        listener_task = self.listener_task
        self.listener_task = None

        if listener_task:

            if (
                listener_task
                is not asyncio.current_task()
            ):

                listener_task.cancel()

                try:

                    await listener_task

                except asyncio.CancelledError:

                    pass

                except Exception as exc:

                    print(
                        "⚠️ TTS listener shutdown warning:",
                        exc,
                    )

        # --------------------------------------------------
        # Close websocket context.
        # --------------------------------------------------

        context = self.ws_context

        self.ws_context = None
        self.ws = None

        if context:

            try:

                await context.__aexit__(
                    None,
                    None,
                    None,
                )

            except Exception as exc:

                print(
                    "⚠️ TTS websocket close warning:",
                    exc,
                )

    # ======================================================
    # INTERRUPT
    #
    # This is the client-side barge-in mechanism.
    #
    # There is no Sarvam in-band cancel message.
    #
    # Therefore:
    #
    # 1. invalidate current generation
    # 2. close websocket
    # 3. discard future audio
    # 4. next speak() creates a fresh connection
    # ======================================================

    async def interrupt(self):

        print(
            "\n🛑 Sarvam TTS interrupt requested"
        )

        # --------------------------------------------------
        # Invalidate all audio belonging to the current
        # generation.
        # --------------------------------------------------

        self.generation += 1

        # --------------------------------------------------
        # Make current speak() completion waitable.
        # --------------------------------------------------

        self.done_event.set()

        # --------------------------------------------------
        # Clear callback so late chunks cannot be played.
        # --------------------------------------------------

        self.audio_callback = None

        # --------------------------------------------------
        # Close current websocket.
        #
        # This is what stops the server-side generation.
        # --------------------------------------------------

        async with self._connect_lock:

            await self._disconnect_ws()

        print(
            "🔌 Sarvam TTS websocket closed"
        )

    # ======================================================
    # SPEAK
    # ======================================================

    async def speak(
        self,
        text,
        on_audio_chunk,
        tts_start,
        should_stop=None,
    ):

        if not text or not text.strip():

            return

        # --------------------------------------------------
        # Every speak() gets its own generation ID.
        # --------------------------------------------------

        self.generation += 1

        generation = self.generation

        self.audio_callback = on_audio_chunk
        self.done_event.clear()

        print(
            f"\n📤 Sending to Sarvam TTS:\n{text}\n"
        )

        async with self.speak_lock:

            # --------------------------------------------------
            # Ensure a fresh websocket exists.
            # --------------------------------------------------

            if (
                self.ws is None
                or self.ws_context is None
            ):

                await self.connect()

            try:

                # --------------------------------------------------
                # Send text.
                # --------------------------------------------------

                await self.ws.convert(
                    text=text
                )

                # --------------------------------------------------
                # Flush tells Sarvam to generate the current
                # buffered text.
                # --------------------------------------------------

                await self.ws.flush()

                # --------------------------------------------------
                # Wait for completion.
                # --------------------------------------------------

                while True:

                    # Barge-in check.
                    if (
                        should_stop
                        and should_stop()
                    ):

                        print(
                            "🛑 TTS detected interruption"
                        )

                        await self.interrupt()

                        return

                    try:

                        await asyncio.wait_for(
                            self.done_event.wait(),
                            timeout=0.25,
                        )

                        break

                    except asyncio.TimeoutError:

                        # Keep checking interruption.
                        continue

            except asyncio.CancelledError:

                print(
                    "🛑 TTS speak task cancelled"
                )

                # Invalidate this generation.
                if self.generation == generation:

                    self.generation += 1

                try:

                    async with self._connect_lock:

                        await self._disconnect_ws()

                except Exception:

                    pass

                raise

            except Exception as exc:

                print(
                    f"❌ TTS websocket error: {exc}"
                )

            finally:

                # --------------------------------------------------
                # Only clean up if this is still our generation.
                # --------------------------------------------------

                if self.generation == generation:

                    self.audio_callback = None

                    async with self._connect_lock:

                        await self._disconnect_ws()

    # ======================================================
    # RECEIVE SARVAM TTS MESSAGES
    # ======================================================

    async def process_messages(self):

        try:

            async for message in self.ws:

                # --------------------------------------------------
                # Ignore messages if websocket was invalidated.
                # --------------------------------------------------

                if self.ws is None:

                    break

                message_type = getattr(
                    message,
                    "type",
                    None,
                )

                # --------------------------------------------------
                # AUDIO
                # --------------------------------------------------

                if message_type == "audio":

                    try:

                        audio_b64 = (
                            message.data.audio
                        )

                        pcm = base64.b64decode(
                            audio_b64
                        )

                        print(f"[TTS] audio chunk received bytes={len(pcm)}")

                    except Exception as exc:

                        print(
                            "❌ TTS audio decode error:",
                            exc,
                        )

                        continue

                    callback = self.audio_callback

                    if callback:

                        try:

                            print(
                                f"[TTS→AUDIO] callback about to run "
                                f"bytes={len(pcm)} callback={callback}"
                            )

                            await callback(pcm)

                            print(
                                f"[TTS→AUDIO] callback completed "
                                f"bytes={len(pcm)}"
                            )

                        except Exception as exc:

                            print(
                                f"[TTS→AUDIO] callback FAILED "
                                f"bytes={len(pcm)} error={exc}"
                            )

                            print(
                                "❌ TTS audio callback error:",
                                exc,
                            )

                # --------------------------------------------------
                # COMPLETION EVENT
                # --------------------------------------------------

                elif message_type == "event":

                    print(
                        f"✅ TTS event: "
                        f"{message.data}"
                    )

                    self.done_event.set()

                # --------------------------------------------------
                # ERROR
                # --------------------------------------------------

                elif message_type == "error":

                    print(
                        f"❌ TTS error: "
                        f"{message.data}"
                    )

                    self.done_event.set()

                else:

                    print(
                        f"⚠️ Unknown TTS message: "
                        f"{message}"
                    )

        except asyncio.CancelledError:

            raise

        except Exception as exc:

            print(
                f"❌ TTS listener error: {exc}"
            )

            self.done_event.set()

    # ======================================================
    # DISCONNECT
    # ======================================================

    async def disconnect(self):

        print(
            "\n🔌 Disconnecting Sarvam TTS..."
        )

        self.generation += 1

        self.audio_callback = None

        self.done_event.set()

        async with self._connect_lock:

            await self._disconnect_ws()

        print(
            "🔴 Sarvam Streaming TTS disconnected"
        )


