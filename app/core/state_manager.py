class StateManager:

    def __init__(self):
        self.state = "IDLE"

    def set_state(self, state):

        self.state = state

        if state == "IDLE":
            print("\n⚪ Ready")

        elif state == "LISTENING":
            print("\n🎤 Listening...")

        elif state == "THINKING":
            print("\n🧠 Thinking...")

        elif state == "SPEAKING":
            print("\n🔊 Speaking...")

        elif state == "ERROR":
            print("\n❌ Error")

    def get_state(self):
        return self.state
