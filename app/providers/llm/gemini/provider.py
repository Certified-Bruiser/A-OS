import os

from google import genai

from app.providers.llm.base import BaseLLM


class GeminiLLM(BaseLLM):

    id = "gemini"
    name = "Gemini"
    models = ["gemini-3.1-flash-lite"]
    default_model = models[0]

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        self.client = genai.Client(api_key=api_key)
        self.agent_configuration = {}

    def configure(self, configuration):
        self.agent_configuration = dict(configuration or {})

    def _input_text(self, prompt, context):
        agent_definition = self.agent_configuration.get("agent_definition", "")
        return f"""{agent_definition}

Conversation history:

{context}

User:

{prompt}"""

    async def stream(self, prompt, context):
        configuration = self.agent_configuration
        model = configuration.get("llmModel") or self.default_model
        input_text = self._input_text(prompt, context)

        stream = await self.client.aio.interactions.create(
            model=model,
            input=input_text,
            stream=True,
            generation_config={
                "thinking_level":"low",
            }
        )

        async for step in stream:
            if getattr(step, "event_type", None) != "step.delta":
                continue

            delta = getattr(step, "delta", None)
            if getattr(delta, "type", None) == "text":
                text = getattr(delta, "text", "")
                if text:
                    yield text

    async def generate_structured(self, prompt, context, schema):
        configuration = self.agent_configuration
        model = configuration.get("llmModel") or self.default_model

        interaction = await self.client.aio.interactions.create(
            model=model,
            input=self._input_text(prompt, context),
            stream=False,
            generation_config={
                "thinking_level":"low",
            },
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": schema,
            },
        )

        return interaction.output_text
