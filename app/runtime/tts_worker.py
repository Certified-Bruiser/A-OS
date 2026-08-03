from app.tts.service import TTSService

from app.runtime.queues import (
    response_queue,
    playback_queue
)


class TTSWorker:

    def __init__(self):

        self.tts = TTSService()

    async def run(self):

        while True:

            response = (
                await response_queue.get()
            )

            print(
                "\n🔊 Generating..."
            )

            audio = await self.tts.synthesize(
                response
            )

            await playback_queue.put(
                audio
            )



