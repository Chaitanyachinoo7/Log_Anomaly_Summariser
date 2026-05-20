from __future__ import annotations

import httpx


async def send_slack(webhook_url: str, text: str) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        resp = await client.post(webhook_url, json={"text": text})
        resp.raise_for_status()

