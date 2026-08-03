from app.audio.service import AudioService
from app.runtime.queue import audio_queue


class ListenerWorker:

    def __init__(self):

        self.audio_service = AudioService()

    async def run(self):

        while True:

            print("\n🎤 Waiting for speech...")

            audio = await self.audio_service.listen()

            await audio_queue.put(audio)

