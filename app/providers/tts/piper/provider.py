from app.providers.tts.base import BaseTTS
from app.tts.service import TTSService


class PiperTTS(BaseTTS):

    id = "piper"
    name = "Piper"

    def __init__(self):
        self.service = TTSService()

    async def speak(
        self,
        text,
        on_audio_chunk,
        tts_start,
        should_stop=None
    ):
        await self.service.speak(
            text=text,
            on_audio_chunk=on_audio_chunk,
            tts_start=tts_start,
            should_stop=should_stop,
        )



