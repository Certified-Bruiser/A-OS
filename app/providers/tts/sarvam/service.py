import os
import asyncio
import base64

from dotenv import load_dotenv
from sarvamai import AsyncSarvamAI

load_dotenv()


class SarvamStreamingTTS:

    def __init__(self):
        self.client = AsyncSarvamAI(
            api_subscription_key=os.getenv("SARVAM_API_KEY")
        )

        self.ws = None
        self.ws_context = None

        self.audio_callback = None
        self.done_event = asyncio.Event()
        self.listener_task = None
        self._connect_lock = asyncio.Lock()

    async def connect(self):
        await self._disconnect_ws()
        self.ws_context = self.client.text_to_speech_streaming.connect(
            model="bulbul:v3",
            send_completion_event=True,
        )

        self.ws = await self.ws_context.__aenter__()

        await self.ws.configure(
            target_language_code="en-IN",
            speaker="rahul",
            output_audio_codec="linear16",
            speech_sample_rate=16000,
        )

        self.listener_task = asyncio.create_task(
            self.process_messages()
        )

        print("🟢 Connected to Sarvam Streaming TTS")

    async def _disconnect_ws(self):
        if self.listener_task:
            listener_task = self.listener_task
            self.listener_task = None
            listener_task.cancel()

            try:
                await listener_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                print(f"TTS listener shutdown warning: {exc}")

        if self.ws_context:
            try:
                await self.ws_context.__aexit__(
                    None,
                    None,
                    None,
                )
            except Exception as exc:
                print(f"TTS disconnect warning: {exc}")
            finally:
                self.ws_context = None
                self.ws = None

    async def speak(
        self,
        text,
        on_audio_chunk,
        tts_start,
        should_stop=None,
    ):
        if not text.strip():
            return

        self.audio_callback = on_audio_chunk
        self.done_event.clear()

        print(f"\n📤 Sending to Sarvam TTS:\n{text}\n")

        async with self._connect_lock:
            if self.ws is None or self.ws_context is None:
                await self.connect()

            try:
                await self.ws.convert(
                    text=text
                )

                await self.ws.flush()

                await asyncio.wait_for(
                    self.done_event.wait(),
                    timeout=30,
                )
            except asyncio.CancelledError:
                await self._disconnect_ws()
                self.done_event.set()
                raise
            except asyncio.TimeoutError:
                print("TTS websocket timed out before completion")
                self.done_event.set()
            finally:
                await self._disconnect_ws()

    async def process_messages(self):
        async for message in self.ws:

            print("\n========== TTS Message ==========")
            print(message)
            print("=================================\n")

            print("Python type:", type(message))

            if hasattr(message, "__dict__"):
                print("Attributes:", message.__dict__)

            if hasattr(message, "type"):
                print("message.type =", message.type)

            if hasattr(message, "data"):
                print("message.data =", message.data)

            #
            # Current parser (may change after we inspect the first message)
            #

            if getattr(message, "type", None) == "audio":

                pcm = base64.b64decode(
                    message.data.audio
                )

                if self.audio_callback:
                    await self.audio_callback(pcm)

            elif getattr(message, "type", None) == "event":

                print(f"TTS Event: {message.data}")

                self.done_event.set()

            elif getattr(message, "type", None) == "error":

                print(f"TTS Error: {message.data}")

                self.done_event.set()

    async def disconnect(self):
        async with self._connect_lock:
            await self._disconnect_ws()

