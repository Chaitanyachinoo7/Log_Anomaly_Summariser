from __future__ import annotations

from typing import Any

import httpx


class OllamaClient:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    async def chat(self, model: str, messages: list[dict[str, Any]]) -> str:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message") or {}
            content = message.get("content")
            if not isinstance(content, str):
                raise RuntimeError("Unexpected Ollama response shape")
            return content

