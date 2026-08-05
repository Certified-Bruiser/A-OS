from app.conversation.state import AssistantState


class StateManager:

    def __init__(self):
        self.state = "IDLE"

    def _normalize_state(self, state):
        if isinstance(state, AssistantState):
            return state.value.upper()

        if isinstance(state, str):
            return state.upper()

        return str(state).upper()

    def set_state(self, state):

        self.state = self._normalize_state(state)

        if self.state == "IDLE":
            print("\n⚪ Ready")

        elif self.state == "LISTENING":
            print("\n🎤 Listening...")

        elif self.state == "THINKING":
            print("\n🧠 Thinking...")

        elif self.state == "SPEAKING":
            print("\n🔊 Speaking...")

        elif self.state == "ERROR":
            print("\n❌ Error")

    def get_state(self):
        return self.state
