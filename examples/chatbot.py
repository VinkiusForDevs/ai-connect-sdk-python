"""
Minimal multi-user chatbot handler.

Each user gets their own capabilities — the same code serves every user. Run
with: `python examples/chatbot.py` (after installing the package and setting
your Vinkius credentials).
"""

from __future__ import annotations

import os

from vinkius_connect import Vinkius

vinkius = Vinkius(
    app_id=os.environ.get("VINKIUS_APP_ID", "vk_app_example"),
    api_key=os.environ.get("VINKIUS_APP_KEY", "vk_app_sk_example"),
)


async def handle_chat(user_id: str, message: str) -> None:
    user = vinkius.user(user_id)

    # The capabilities this specific user has connected.
    capabilities = await user.capabilities()

    # Hand `capabilities` to your agent/LLM framework. Here we just print them.
    print(
        f"user={user_id} message={message} "
        f"capabilities={', '.join(c.name for c in capabilities)}"
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(handle_chat("alice_123", "Open a GitHub issue titled 'Ship it'"))
