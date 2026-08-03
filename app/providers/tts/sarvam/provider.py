from app.providers.tts.base import BaseTTS
from app.providers.tts.sarvam.service import SarvamStreamingTTS


class SarvamTTS(BaseTTS):

    id = "sarvam"
    name = "Sarvam Streaming"

    def __init__(self):
        self.service = SarvamStreamingTTS()

    async def connect(self):
        await self.service.connect()

    async def disconnect(self):
        await self.service.disconnect()

    async def speak(
        self,
        text,
        on_audio_chunk,
        tts_start,
        should_stop=None,
    ):
        await self.service.speak(
            text=text,
            on_audio_chunk=on_audio_chunk,
            tts_start=tts_start,
            should_stop=should_stop,
        )

