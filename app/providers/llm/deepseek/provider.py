import json
import os

from openai import AsyncOpenAI

from app.providers.llm.base import BaseLLM


class DeepSeekLLM(BaseLLM):

    id = "deepseek"
    name = "DeepSeek"
    models = ["deepseek-flash", "deepseek-v4-pro"]
    default_model = "deepseek-flash"

    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        self.agent_configuration = {}

    def configure(self, configuration):
        self.agent_configuration = dict(configuration or {})

    async def stream(self, prompt, context):
        configuration = self.agent_configuration
        model = configuration.get("llmModel") or self.default_model
        agent_definition = configuration.get("agent_definition", "")

        messages = [
            {
                "role": "system",
                "content": agent_definition,
            },
            {
                "role": "user",
                "content": f"""Conversation history:

{context}

User:

{prompt}""",
            },
        ]

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            reasoning_effort="none",
            extra_body={
                "thinking": {
                    "type": "disabled",
                },
            },
        )

        async for chunk in response:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                yield text

    async def generate_structured(self, prompt, context, schema):
        configuration = self.agent_configuration
        model = configuration.get("llmModel") or self.default_model
        agent_definition = configuration.get("agent_definition", "")

        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": agent_definition,
                },
                {
                    "role": "user",
                    "content": f"""Conversation history:

{context}

User:

{prompt}

Return only valid JSON matching this schema:
{json.dumps(schema)}""",
                },
            ],
            stream=False,
            reasoning_effort="none",
            extra_body={
                "thinking": {
                    "type": "disabled",
                },
            },
            response_format={
                "type": "json_object",
            },
        )

        return response.choices[0].message.content or ""
