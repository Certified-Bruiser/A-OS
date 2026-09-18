from app.providers.llm.base import BaseLLM
from app.llm.service import LLMService


class PerplexityLLM(BaseLLM):

    id = "perplexity"
    name = "Perplexity Sonar"
    models = ["sonar"]

    def __init__(self):
        self.service = LLMService()
        print("[PROVIDER] PerplexityLLM instantiated through ProviderFactory")

    def configure(self, configuration):
        self.service.configure(configuration)

    async def stream(self, prompt, context):
        async for token in self.service.stream(prompt, context):
            yield token

    async def generate_structured(self, prompt, context, schema):
        return await self.service.generate_structured(prompt, context, schema)

