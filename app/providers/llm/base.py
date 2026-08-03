from abc import ABC, abstractmethod


class BaseLLM(ABC):

    id = ""
    name = ""

    @abstractmethod
    async def stream(self, prompt, context):
        yield ""
