from datetime import datetime
import uuid


class SessionManager:

    def __init__(self):
        self.session_id = None
        self.started_at = None
        self.ended_at = None

    def start(self):
        self.session_id = str(uuid.uuid4())

        self.started_at = datetime.utcnow().isoformat()

        self.ended_at = None

    def end(self):
        self.ended_at = datetime.utcnow().isoformat()

    def metadata(self):
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }

    def active(self):
        return self.session_id is not None and self.ended_at is None
