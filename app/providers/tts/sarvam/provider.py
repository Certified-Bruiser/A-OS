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

    async def interrupt(self):
        """
        Interrupt the current Sarvam TTS generation.

        Sarvam has no in-band cancel message.
        Closing the current websocket is the cancellation.
        """

        await self.service.interrupt()

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

    async def interrupt(self):
        print(
        "\n🛑 Sarvam TTS interrupt"
    )

    # Wake speak() if it is waiting for completion.
        self.done_event.set()

    # Closing the websocket is the actual
    # server-side cancellation mechanism.
        await self._disconnect_ws()



