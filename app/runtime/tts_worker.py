import time

from app.tts.service import TTSService

from app.runtime.queue import (
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

            chunks = []

            async def capture_chunk(chunk):
                chunks.append(chunk)

            await self.tts.speak(
                response,
                on_audio_chunk=capture_chunk,
                tts_start=time.perf_counter(),
                should_stop=None,
            )

            await playback_queue.put(
                b"".join(chunks)
            )



