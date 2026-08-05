from app.llm.service import LLMService
from app.memory.service import MemoryService

from app.runtime.queue import (
    transcript_queue,
    response_queue
)


class LLMWorker:

    def __init__(self):

        self.llm = LLMService()
        self.memory = MemoryService()

    async def run(self):

        while True:

            transcript = (
                await transcript_queue.get()
            )

            print("\n🧠 Thinking...")

            self.memory.save_message(
                "user",
                transcript
            )

            response = await self.llm.generate(
                transcript,
                self.memory.get_context()
            )

            self.memory.save_message(
                "assistant",
                response
            )

            await response_queue.put(
                response
            )
