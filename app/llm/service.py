import os
from openai import AsyncOpenAI


class LLMService:


    def __init__(self):

        self.client = AsyncOpenAI(
            api_key=os.getenv(
                "PERPLEXITY_API_KEY"
            ),
            base_url="https://api.perplexity.ai"
        )



    async def is_running(self):

        return bool(
            os.getenv("PERPLEXITY_API_KEY")
        )



    async def stream(

        self,

        prompt: str,

        conversation_context=""

    ):


        system_prompt = """
You are Jarvis.

You are a voice assistant.

Keep responses concise and it will be spoken aloud.

Maximum 3 sentences.

Do not use:
- emojis
- markdown
- bullet points
- asterisks
- hashtags
- code blocks
- URLs unless the user explicitly asks for one

Speak naturally and respond in plain conversational english.


Always end with a question.
"""



        response = await self.client.chat.completions.create(

            model="sonar",

            messages=[

                {
                    "role": "system",
                    "content": system_prompt
                },

                {
                    "role": "user",
                    "content": f"""
Conversation history:

{conversation_context}


User:

{prompt}
"""
                }

            ],

            stream=True

        )



        async for chunk in response:


            token = (
                chunk
                .choices[0]
                .delta
                .content
            )


            if token:

                yield token



    async def close(self):

        await self.client.close()
