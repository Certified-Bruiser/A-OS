from app.providers.stt.base import BaseSTT
from app.stt.service import STTService


class SarvamSTT(BaseSTT):

    id = "sarvam"
    name = "Sarvam AI"

    def __init__(self):
        self.service = STTService()

    async def connect(self):
        return await self.service.connect()

    async def disconnect(self):
        return await self.service.disconnect()

    async def transcribe(self, audio):
        return await self.service.transcribe(audio)

