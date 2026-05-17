import httpx
import os
import asyncio
from typing import AsyncGenerator

HERMES_GATEWAY_URL = os.getenv("HERMES_GATEWAY_URL", "http://localhost:5000/api/chat")
HERMES_MCP_URL     = os.getenv("HERMES_MCP_URL", "http://localhost:8001/mcp")
HERMES_API_KEY     = os.getenv("HERMES_API_KEY", "")


async def query_hermes(user_message: str, context: str) -> AsyncGenerator[str, None]:
    """
    Streams a response from the Hermes agent.
    Hermes runs as a separate process (local or VPS).
    Falls back to a mock if Hermes is not running.
    """
    payload = {
        "message": f"{context}\n\nUser question: {user_message}",
        "skill": "accounting-my",
        "stream": True,
    }
    headers = {}
    if HERMES_API_KEY:
        headers["Authorization"] = f"Bearer {HERMES_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", HERMES_GATEWAY_URL, json=payload, headers=headers) as r:
                async for chunk in r.aiter_text():
                    yield f"data: {chunk}\n\n"
    except Exception as e:
        # Hermes not running — yield a clear explanation
        yield f"data: Hermes agent not connected ({str(e)}). Start Hermes with: hermes gateway start\n\n"


async def call_mcp_tool(tool_name: str, params: dict) -> dict:
    """
    Calls a specific MCP tool on the Hermes accounting MCP server.
    Used by the nightly cron skill and autonomous document processing.
    """
    payload = {
        "tool": tool_name,
        "params": params,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{HERMES_MCP_URL}/call", json=payload)
        return response.json()
