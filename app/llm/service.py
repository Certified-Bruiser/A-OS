import os
import time
from openai import AsyncOpenAI


class LLMService:

    def __init__(self):
        self.agent_configuration = {}

        self.client = AsyncOpenAI(
            api_key=os.getenv("PERPLEXITY_API_KEY"),
            base_url="https://api.perplexity.ai",
        )
        
        # --------------------------------------------------
        # Latency timing (set by agent runtime)
        # --------------------------------------------------
        
        self.turn_timing = None

    # ======================================================
    # AGENT CONFIGURATION
    # ======================================================

    def configure(self, configuration):
        self.agent_configuration = dict(configuration or {})

        print("\n" + "=" * 60)
        print("⚙️ LLM CONFIGURED")
        print("   Agent:", self.agent_configuration.get("name", "unknown"))
        print(
            "   Provider:",
            self.agent_configuration.get("llmProvider", "perplexity"),
        )
        print(
            "   Model:",
            self.agent_configuration.get("llmModel", "sonar"),
        )
        print("=" * 60)

    # ======================================================
    # SYSTEM PROMPT
    # ======================================================

    def _agent_system_prompt(self):
        configuration = self.agent_configuration

        agent_definition = configuration.get(
            "agent_definition"
        )

        sections = [
            agent_definition or "",
            "Answer the user's request accurately and stay within your configured purpose. "
            "Do not discuss restricted topics, and escalate or hand off when the instructions require it."
        ]

        return "\n".join(filter(None, sections))

    # ======================================================
    # RUNNING STATUS
    # ======================================================

    async def is_running(self):
        return bool(
            os.getenv("PERPLEXITY_API_KEY")
        )

    # ======================================================
    # STREAM LLM RESPONSE
    # ======================================================

    async def stream(
        self,
        prompt: str,
        conversation_context="",
    ):

        model = self.agent_configuration.get(
            "llmModel",
            "sonar",
        )

        agent_name = self.agent_configuration.get(
            "name",
            "unknown",
        )

        print("[LLM] stream() called")
        print(
            f"[LLM] provider={self.agent_configuration.get('llmProvider', 'perplexity')}"
        )
        print(f"[LLM] model={model}")
        print("[LLM] calling provider")

        # --------------------------------------------------
        # DEBUG
        # --------------------------------------------------

        print("\n" + "=" * 60)
        print("🤖 LLM CALLED")
        print("   Provider: Perplexity")
        print("   Model:", model)
        print("   Agent:", agent_name)
        print("   User:", prompt)
        print("=" * 60)

        # --------------------------------------------------
        # BUILD AGENT-SPECIFIC SYSTEM PROMPT
        # --------------------------------------------------

        system_prompt = self._agent_system_prompt()

        print("🧠 Agent system prompt loaded")

        # --------------------------------------------------
        # CALL PERPLEXITY
        # --------------------------------------------------

        try:

            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": f"""
Conversation history:

{conversation_context}

User:

{prompt}
""",
                    },
                ],
                stream=True,
            )

            print("✅ Perplexity request accepted")
            print("[LLM] response received")

        except Exception as e:

            print("\n❌ LLM REQUEST FAILED")
            print("   Provider: Perplexity")
            print("   Model:", model)
            print("   Error:", repr(e))
            print("=" * 60)

            raise

        # --------------------------------------------------
        # STREAM RESPONSE
        # --------------------------------------------------

        try:
            
            first_token_recorded = False

            async for chunk in response:

                if not chunk.choices:
                    continue

                token = (
                    chunk
                    .choices[0]
                    .delta
                    .content
                )

                if token:
                    
                    # Record first token time
                    if (not first_token_recorded and 
                        self.turn_timing):
                        self.turn_timing.llm_first_token = time.perf_counter()
                        first_token_recorded = True

                    print(
                        token,
                        end="",
                        flush=True,
                    )

                    yield token

            print("\n\n✅ LLM STREAM COMPLETE")
            print("=" * 60)
            
            # Record LLM complete time
            if self.turn_timing:
                self.turn_timing.llm_complete = time.perf_counter()

        except Exception as e:

            print("\n❌ LLM STREAM FAILED")
            print("   Error:", repr(e))
            print("=" * 60)

            raise

    # ======================================================
    # CLOSE
    # ======================================================

    async def close(self):

        await self.client.close()

