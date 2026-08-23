from app.providers.stt.base import BaseSTT
from app.stt.service import STTService


class SarvamSTT(BaseSTT):

    id = "sarvam"
    name = "Sarvam Streaming"

    def __init__(self):

        self.service = STTService()

    # ======================================================
    # CONNECT
    # ======================================================

    async def connect(self):

        await self.service.connect()

    # ======================================================
    # DISCONNECT
    # ======================================================

    async def disconnect(self):

        await self.service.disconnect()

    # ======================================================
    # CONTINUOUS MICROPHONE AUDIO
    # ======================================================

    async def feed_audio(
        self,
        pcm: bytes
    ):

        await self.service.feed_audio(
            pcm
        )

    # ======================================================
    # WAIT FOR USER TRANSCRIPT
    # ======================================================

    async def wait_for_transcript(
        self,
        timeout=10
    ):

        return await self.service.wait_for_transcript(
            timeout=timeout
        )

    # ======================================================
    # PREPARE FOR NEW TURN
    # ======================================================

    async def prepare_for_turn(self):

        await self.service.prepare_for_turn()

    # ======================================================
    # WAIT FOR SPEECH START
    # ======================================================

    async def wait_for_speech_start(
        self,
        timeout=None
    ):

        return await self.service.wait_for_speech_start(
            timeout=timeout
        )

    # ======================================================
    # WAIT FOR SPEECH END
    # ======================================================

    async def wait_for_speech_end(
        self,
        timeout=10
    ):

        return await self.service.wait_for_speech_end(
            timeout=timeout
        )

    # ======================================================
    # LEGACY TRANSCRIBE
    #
    # Kept so older code doesn't immediately break.
    # ======================================================

    async def transcribe(
        self,
        wav_bytes: bytes
    ):

        return await self.service.transcribe(
            wav_bytes
        )


