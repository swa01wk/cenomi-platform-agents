from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import aiofiles

REGISTRY_PATH = Path("agents/registry/agents.json")

class AgentRegistryStore:
    def __init__(self, path: Path = REGISTRY_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"agents": []}, indent=2), encoding="utf-8")

    def _read(self) -> Dict[str, Any]:
        raw = self.path.read_text(encoding="utf-8").strip()

        # File exists but empty (0 bytes / whitespace)
        if not raw:
            data = {"agents": []}
            self._write(data)
            return data

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Corrupted/partial JSON — reset for PoC
            data = {"agents": []}
            self._write(data)
            return data

        # Normalize structure
        if not isinstance(data, dict):
            data = {"agents": []}
            self._write(data)
            return data

        if "agents" not in data or not isinstance(data["agents"], list):
            data["agents"] = []
            self._write(data)

        return data

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def list_agents(self) -> List[Dict[str, Any]]:
        return self._read()["agents"]

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return next((a for a in self.list_agents() if a["agent_id"] == agent_id), None)

    def create_agent(self, agent: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read()
        if any(a["agent_id"] == agent["agent_id"] for a in data["agents"]):
            raise ValueError(f"Agent '{agent['agent_id']}' already exists")
        data["agents"].append(agent)
        self._write(data)
        return agent

    def update_agent(self, agent_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read()
        for i, a in enumerate(data["agents"]):
            if a["agent_id"] == agent_id:
                updated = dict(a)
                for k, v in patch.items():
                    if v is not None:
                        updated[k] = v
                data["agents"][i] = updated
                self._write(data)
                return updated
        raise KeyError(f"Agent '{agent_id}' not found")

    def delete_agent(self, agent_id: str) -> None:
        data = self._read()
        before = len(data["agents"])
        data["agents"] = [a for a in data["agents"] if a["agent_id"] != agent_id]
        if len(data["agents"]) == before:
            raise KeyError(f"Agent '{agent_id}' not found")
        self._write(data)

    # Async methods
    async def _aread(self) -> Dict[str, Any]:
        async with aiofiles.open(self.path, 'r', encoding='utf-8') as f:
            raw = (await f.read()).strip()

        # File exists but empty (0 bytes / whitespace)
        if not raw:
            data = {"agents": []}
            await self._awrite(data)
            return data

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Corrupted/partial JSON — reset for PoC
            data = {"agents": []}
            await self._awrite(data)
            return data

        # Normalize structure
        if not isinstance(data, dict):
            data = {"agents": []}
            await self._awrite(data)
            return data

        if "agents" not in data or not isinstance(data["agents"], list):
            data["agents"] = []
            await self._awrite(data)

        return data

    async def _awrite(self, data: Dict[str, Any]) -> None:
        async with aiofiles.open(self.path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2))

    async def alist_agents(self) -> List[Dict[str, Any]]:
        data = await self._aread()
        return data["agents"]

    async def aget_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        agents = await self.alist_agents()
        return next((a for a in agents if a["agent_id"] == agent_id), None)

    async def acreate_agent(self, agent: Dict[str, Any]) -> Dict[str, Any]:
        data = await self._aread()
        if any(a["agent_id"] == agent["agent_id"] for a in data["agents"]):
            raise ValueError(f"Agent '{agent['agent_id']}' already exists")
        data["agents"].append(agent)
        await self._awrite(data)
        return agent

    async def aupdate_agent(self, agent_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        data = await self._aread()
        for i, a in enumerate(data["agents"]):
            if a["agent_id"] == agent_id:
                updated = dict(a)
                for k, v in patch.items():
                    if v is not None:
                        updated[k] = v
                data["agents"][i] = updated
                await self._awrite(data)
                return updated
        raise KeyError(f"Agent '{agent_id}' not found")

    async def adelete_agent(self, agent_id: str) -> None:
        data = await self._aread()
        before = len(data["agents"])
        data["agents"] = [a for a in data["agents"] if a["agent_id"] != agent_id]
        if len(data["agents"]) == before:
            raise KeyError(f"Agent '{agent_id}' not found")
        await self._awrite(data)
