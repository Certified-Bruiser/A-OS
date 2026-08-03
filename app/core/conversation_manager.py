class ConversationManager:

    def __init__(self):
        self.history = []

    def add_user_message(
        self,
        message
    ):

        self.history.append(
            {
                "role": "user",
                "content": message
            }
        )

    def add_assistant_message(
        self,
        message
    ):

        self.history.append(
            {
                "role": "assistant",
                "content": message
            }
        )

    def get_context(self):

        context = ""

        for message in self.history[-10:]:

            context += (
                f"{message['role']}: "
                f"{message['content']}\n"
            )

        return context
