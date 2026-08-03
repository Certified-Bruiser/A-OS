import os
import base64
import asyncio

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

        self.ws = None
        self.ws_context = None

        self.transcript = ""

        self.transcript_event = asyncio.Event()

    async def connect(self):

        self.ws_context = self.client.speech_to_text_streaming.connect(
            model="saaras:v3",
            language_code="en-IN",
            mode="transcribe",
            high_vad_sensitivity=True,
            vad_signals=True
        )

        self.ws = await self.ws_context.__aenter__()

        print("\n🟢 Connected to SarvamAI")

        self.listener_task = asyncio.create_task(
            self.process_messages()
        )

    async def transcribe(
        self,
        wav_bytes: bytes
    ):

        self.transcript = ""

        self.transcript_event.clear()

        encoded_audio = base64.b64encode(
            wav_bytes
        ).decode("utf-8")

        print("\n📤 Sending audio to SarvamAI...")

        await self.ws.transcribe(
            audio=encoded_audio,
            sample_rate=16000,
            encoding="audio/wav"
        )

        await self.ws.flush()

        print("\n⏳ Waiting for transcript...")

        try:

            await asyncio.wait_for(
                self.transcript_event.wait(),
                timeout=20
            )

        except asyncio.TimeoutError:

            print(
                "\n❌ Transcript timeout"
            )

            return ""

        return self.transcript.strip()

    async def process_messages(self):

        async for message in self.ws:

            if message.type == "events":

                signal = message.data.signal_type

                print(
                    f"\n🎙️ {signal}"
                )

                if signal == "START_SPEECH":

                    self.state_manager.set_state(
                        "LISTENING"
                    )

                elif signal == "END_SPEECH":

                    self.state_manager.set_state(
                        "PROCESSING"
                    )

            elif message.type == "data":

                self.transcript = (
                    message.data.transcript
                )

                print(
                    f"\n📝 {self.transcript}"
                )

                self.transcript_event.set()

    async def disconnect(self):

        if self.listener_task:

            self.listener_task.cancel()

        if self.ws_context:

            await self.ws_context.__aexit__(
                None,
                None,
                None
            )

