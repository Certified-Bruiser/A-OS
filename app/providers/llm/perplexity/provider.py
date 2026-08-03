from app.providers.llm.base import BaseLLM
from app.llm.service import LLMService


class PerplexityLLM(BaseLLM):

    id = "perplexity"
    name = "Perplexity Sonar"

    def __init__(self):
        self.service = LLMService()

    async def stream(self, prompt, context):
        async for token in self.service.stream(prompt, context):
            yield token

