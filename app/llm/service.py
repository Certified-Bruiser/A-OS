import os
from openai import AsyncOpenAI


class LLMService:

    def __init__(self):
        self.agent_configuration = {}

        self.client = AsyncOpenAI(
            api_key=os.getenv("PERPLEXITY_API_KEY"),
            base_url="https://api.perplexity.ai",
        )

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

        name = configuration.get(
            "name",
            "the assistant",
        )

        purpose = (
            configuration.get("purpose")
            or configuration.get("goal")
            or configuration.get("goals", "")
        )

        instructions = configuration.get(
            "systemInstructions",
            "",
        )

        personality = configuration.get(
            "personality",
            "",
        )

        tone = configuration.get(
            "tone",
            "",
        )

        style = configuration.get(
            "conversationStyle",
            "",
        )

        allowed_topics = configuration.get("allowedTopics", [])
        restricted_topics = configuration.get("restrictedTopics", [])
        escalation_rules = configuration.get("escalationRules", "")
        human_handoff_conditions = configuration.get("humanHandoffConditions", "")
        require_confirmation = bool(configuration.get("requireConfirmation", False))

        sections = [
            f"You are {name}.",
            f"Your purpose is: {purpose}" if purpose else "",
            f"System instructions: {instructions}" if instructions else "",
            f"Personality: {personality}" if personality else "",
            f"Tone: {tone}" if tone else "",
            f"Conversation style: {style}" if style else "",
        ]

        if allowed_topics:
            sections.append("Allowed topics: " + ", ".join(str(item) for item in allowed_topics if str(item).strip()))
        if restricted_topics:
            sections.append("Restricted topics: " + ", ".join(str(item) for item in restricted_topics if str(item).strip()))
        if escalation_rules:
            sections.append(f"Escalation rules: {escalation_rules}")
        if human_handoff_conditions:
            sections.append(f"Human handoff conditions: {human_handoff_conditions}")
        if require_confirmation:
            sections.append("Require confirmation before taking actions that change data, schedule bookings, send messages, or otherwise affect the user or account.")

        sections.append(
            "Answer the user's request accurately and stay within your configured purpose. "
            "Do not discuss restricted topics, and escalate or hand off when the instructions require it."
        )

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

                    print(
                        token,
                        end="",
                        flush=True,
                    )

                    yield token

            print("\n\n✅ LLM STREAM COMPLETE")
            print("=" * 60)

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

