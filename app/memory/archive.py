import json
from pathlib import Path


class ConversationArchive:

    def __init__(self):
        self.storage = Path(
            "app/memory/storage/conversations"
        )

        self.storage.mkdir(
            parents=True,
            exist_ok=True
        )

    def save(
        self,
        session_metadata,
        messages,
    ):

        filename = (
            f"{session_metadata['session_id']}.json"
        )

        path = self.storage / filename

        data = {
            **session_metadata,
            "conversation": messages,
        }

        with open(
            path,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False,
            )

    def load(
        self,
        session_id,
    ):

        path = self.storage / f"{session_id}.json"

        if not path.exists():
            return None

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    def list_sessions(self):

        sessions = []

        for file in sorted(
            self.storage.glob("*.json")
        ):
            sessions.append(file.stem)

        return sessions

