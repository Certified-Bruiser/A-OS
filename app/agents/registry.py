import json
from pathlib import Path
from dataclasses import asdict

from app.agents.model import Agent


class AgentRegistry:

    def __init__(self):

        self.storage_path = Path(
            "data/agents"
        )

        self.storage_path.mkdir(
            parents=True,
            exist_ok=True
        )

    def save(self, agent: Agent):

        file_path = (
            self.storage_path /
            f"{agent.id}.json"
        )

        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                asdict(agent),
                file,
                indent=4
            )

    def get(self, agent_id: str):

        file_path = (
            self.storage_path /
            f"{agent_id}.json"
        )

        if not file_path.exists():
            return None

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        return Agent(**data)

    def list_agents(self):

        agents = []

        for file in self.storage_path.glob("*.json"):

            with open(
                file,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

                agents.append(
                    Agent(**data)
                )

        return agents
