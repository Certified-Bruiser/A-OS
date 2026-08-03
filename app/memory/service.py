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

    def start_session(self):

        self.working.clear()

        self.session.start()

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

    def remember(self, fact):

        self.long_term.remember(fact)

    def memories(self):

        return self.long_term.all()

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
