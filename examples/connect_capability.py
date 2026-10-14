"""
"Connect your GitHub" flow: connect the connector -> set credentials -> check readiness.

Run with your real credentials:

    export VINKIUS_APP_ID=vk_app_xxx
    export VINKIUS_APP_KEY=vk_app_sk_xxx
    python examples/connect_capability.py
"""

from __future__ import annotations

import os

from vinkius_connect import Vinkius

vinkius = Vinkius(
    app_id=os.environ.get("VINKIUS_APP_ID", "vk_app_example"),
    api_key=os.environ.get("VINKIUS_APP_KEY", "vk_app_sk_example"),
)


async def connect_github(user_id: str, github_token: str) -> None:
    github = vinkius.user(user_id).connector("github")

    await github.connect()
    schema = await github.credentials.schema()
    await github.credentials.set({"GITHUB_TOKEN": github_token})

    status = await github.status()
    # status -> not_connected | needs_credentials | ready | disabled
    print(f"github status={status} requires={','.join(schema)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(connect_github("alice_123", "ghp_example"))
