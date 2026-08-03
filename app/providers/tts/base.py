from abc import ABC, abstractmethod


class BaseTTS(ABC):

    id = ""
    name = ""

    streaming = False

    @abstractmethod
    async def speak(
        self,
        text,
        on_audio_chunk,
        tts_start,
        should_stop=None,
    ):
        pass
