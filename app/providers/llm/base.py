from abc import ABC, abstractmethod


class BaseLLM(ABC):

    id = ""
    name = ""

    @abstractmethod
    async def stream(self, prompt, context):
        yield ""

    async def generate_structured(self, prompt, context, schema):
        response_parts = []

        async for text in self.stream(prompt, context):
            response_parts.append(text)

        return "".join(response_parts).strip()
