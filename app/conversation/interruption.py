from dataclasses import dataclass


@dataclass
class InterruptionResult:
    interrupt: bool
    transcript: str | None = None


class InterruptionService:

    def __init__(self, stt):
        self.stt = stt

    async def detect(self, audio: bytes) -> InterruptionResult:

        transcript = await self.stt.transcribe(audio)

        if not transcript:
            return InterruptionResult(
                interrupt=False
            )

        transcript = transcript.strip()

        if transcript == "":
            return InterruptionResult(
                interrupt=False
            )

        return InterruptionResult(
            interrupt=True,
            transcript=transcript
        )

