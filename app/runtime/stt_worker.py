from app.stt.service import STTService
from app.runtime.queues import (
    audio_queue,
    transcript_queue
)


class STTWorker:

    def __init__(self):

        self.stt = STTService()

    async def run(self):

        await self.stt.connect()

        while True:

            audio = await audio_queue.get()

            transcript = await self.stt.transcribe(
                audio
            )

            if transcript:

                print(
                    f"\n📝 {transcript}"
                )

                await transcript_queue.put(
                    transcript
                )
