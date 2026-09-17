from app.memory.working_memory import WorkingMemory
from app.memory.session import SessionManager
from app.memory.archive import ConversationArchive
from app.memory.long_term import LongTermMemory


class MemoryService:

    def __init__(self):

        self.working = WorkingMemory()

        self.session = SessionManager()

        self.archive = ConversationArchive()

        self.long_term = LongTermMemory()

    # -----------------------------
    # Session
    # -----------------------------

    def start_session(self, agent_id=None, user_id=None):

        self.working.clear()

        self.session.start(agent_id=agent_id, user_id=user_id)

    def end_session(self):

        self.session.end()

        self.archive.save(
            self.session.metadata(),
            self.working.get_messages(),
        )

        self.working.clear()

    # -----------------------------
    # Working Memory
    # -----------------------------

    def save_message(
        self,
        role,
        content,
    ):

        self.working.add(
            role,
            content,
        )

    def get_context(self):

        return self.working.get_context()

    # -----------------------------
    # Long-Term Memory
    # -----------------------------

    def remember(self, category, key, value, source="user", confidence=1.0):

        return self.long_term.remember(
            agent_id=self.session.agent_id,
            user_id=self.session.user_id,
            category=category,
            key=key,
            value=value,
            source=source,
            confidence=confidence,
        )

    def memories(self):

        return self.long_term.list(
            agent_id=self.session.agent_id,
            user_id=self.session.user_id,
        )

    def update_memory(self, memory_id, **changes):
        return self.long_term.update(
            memory_id,
            self.session.agent_id,
            self.session.user_id,
            **changes,
        )

    def replace_memory(self, category, key, value, source="user", confidence=1.0):
        return self.long_term.replace(
            self.session.agent_id,
            self.session.user_id,
            category,
            key,
            value,
            source,
            confidence,
        )

    def forget_memory(self, memory_id):
        return self.long_term.forget(
            memory_id,
            self.session.agent_id,
            self.session.user_id,
        )

    # -----------------------------
    # Archive
    # -----------------------------

    def sessions(self):

        return self.archive.list_sessions()

    def load_session(
        self,
        session_id,
    ):

        return self.archive.load(
            session_id
        )
