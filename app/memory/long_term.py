import json
from pathlib import Path


class LongTermMemory:

    def __init__(self):
        self.file = Path(
            "app/memory/storage/long_term.json"
        )

        self.file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.file.exists():
            with open(
                self.file,
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    {
                        "memories": []
                    },
                    f,
                    indent=4,
                    ensure_ascii=False,
                )

    def _load(self):

        with open(
            self.file,
            "r",
            encoding="utf-8",
        ) as f:

            return json.load(f)

    def _save(self, data):

        with open(
            self.file,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False,
            )

    def remember(self, fact):

        data = self._load()

        if fact not in data["memories"]:
            data["memories"].append(fact)

            self._save(data)

    def all(self):

        return self._load()["memories"]

    def forget(self, fact):

        data = self._load()

        if fact in data["memories"]:

            data["memories"].remove(fact)

            self._save(data)

    def clear(self):

        self._save(
            {
                "memories": []
            }
        )
