from abc import ABC, abstractmethod


class BaseSTT(ABC):

    id = ""
    name = ""

    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def transcribe(self, audio: bytes) -> str:
        pass
