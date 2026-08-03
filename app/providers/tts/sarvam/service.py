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

    async def connect(self):
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

        await self.ws.convert(
            text=text
        )

        await self.ws.flush()

        await self.done_event.wait()

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
        if self.listener_task:
            self.listener_task.cancel()

            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass

        if self.ws_context:
            await self.ws_context.__aexit__(
                None,
                None,
                None,
            )

