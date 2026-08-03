class WorkingMemory:

    def __init__(self):
        self.messages = []

    def add(self, role, content):
        self.messages.append({
            "role": role,
            "content": content
        })

    def get_messages(self):
        return self.messages

    def get_context(self, limit=20):
        context = ""

        for message in self.messages[-limit:]:
            context += (
                f"{message['role']}: "
                f"{message['content']}\n"
            )

        return context

    def clear(self):
        self.messages.clear()

    def count(self):
        return len(self.messages)

