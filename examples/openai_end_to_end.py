"""
End-to-end with OpenAI: three imports, and the model calls your user's real
capabilities.

Requires `pip install openai` (the adapter itself is zero-dependency; it just
shapes the tools; bring your own OpenAI client).

    export VINKIUS_APP_ID=vk_app_xxx
    export VINKIUS_APP_KEY=vk_app_sk_xxx
    export OPENAI_API_KEY=sk_...
    export OPENAI_MODEL=your-model
    python examples/openai_end_to_end.py
"""

from __future__ import annotations

import os

import openai  # pip install openai

from vinkius_connect import Vinkius
from vinkius_connect.adapters import openai as vinkius_openai


async def main() -> None:
    client = openai.AsyncOpenAI()
    vinkius = Vinkius(
        app_id=os.environ["VINKIUS_APP_ID"],
        api_key=os.environ["VINKIUS_APP_KEY"],
    )

    capabilities = await vinkius.user("alice_123").capabilities()

    completion = await client.chat.completions.create(
        model=os.environ["OPENAI_MODEL"],
        messages=[{"role": "user", "content": 'Open a GitHub issue titled "Ship it"'}],
        tools=vinkius_openai.to_openai_tools(capabilities),
    )

    call = completion.choices[0].message.tool_calls[0] if completion.choices else None
    if call:
        result = await vinkius_openai.run_openai_tool_call(capabilities, call)
        print(result.content)

    await vinkius.aclose()
    await client.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
