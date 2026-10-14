<div align="center">

# Vinkius Connect — Python SDK

### Ship AI that _acts_ for each of your users — not just AI that talks.

[![Connectors](https://api.vinkius.com/badges/connectors.svg)](https://vinkius.com)
[![AI Capabilities](https://api.vinkius.com/badges/capabilities.svg)](https://vinkius.com)

</div>

---

## Why you're here

You're building an AI product. Your model is smart, but by itself it can only
_do_ what you hard-code: answer, summarize, draft. The moment you want it to
**take real action for your users** — open a ticket in their repo, post to their
workspace, file a report, move a task — you hit the **integration tax**:

For every external system your agent can touch, you'd otherwise need to build and
maintain, **per user**:

- ❌ OAuth flows and token refresh
- ❌ Where and how to **store** each user's secrets safely
- ❌ Per-user **permissions** ("what can *this* user's agent do?")
- ❌ Protocol glue (MCP, OpenAI tools, Anthropic blocks, …)
- ❌ Endless **API churn** — the vendor changes the API and your integration breaks

That's weeks of unglamorous plumbing *per integration*, and it multiplies with
every new user and every new tool. It's also exactly the part that's boring to
ship and dangerous to get wrong (leaked tokens, cross-user data leaks, revoked
credentials).

## What Vinkius Connect gives you

**Vinkius Connect is a managed connectivity layer for AI builders.** It turns your
single application into a platform where **every end-user gets their own isolated
connectors and capabilities** — and you get them as a clean, framework-neutral set
of tools your agent can call.

You identify the user. Vinkius handles the connectivity, authentication,
permissions, protocols, and execution behind the scenes.

```
Your AI Application
        │
        ▼
      User   ← you already know who this is (your own user id)
        │
        ▼
   Connectors   ← systems that user connected (GitHub, Slack, …)
        │
        ▼
   Capabilities   ← the actions your agent can now take for that user
        │
        ▼
      Action
```

### The core win, in one line

```python
capabilities = await vinkius.user("alice_123").capabilities()
# -> every real action alice's connectors allow, as ready-to-call tools
```

That's it. One call hands your agent the full, **user-scoped** set of capabilities,
and each one is executable. No OAuth, no token vault, no per-integration code.

## What's in it for you (the AI builder)

- **Build product, not plumbing.** Point your agent at `user.capabilities()` and
  it can act across every system your users connected — without you writing a
  single OAuth flow or secret store.
- **Per-user isolation by default.** Each user's connectors and credentials are
  siloed; one user's agent can never act through another's. You inherit security
  properties you'd otherwise have to design and audit yourself.
- **Thousands of maintained connectors.** Vinkius maintains the integrations,
  including their API churn. You get new capabilities when Vinkius adds them —
  not when you get around to patching a broken integration.
- **Portable across your stack.** The same capabilities feed OpenAI, Anthropic,
  Gemini, LangChain, LlamaIndex, OpenAI Agents, or CrewAI. Swap models or agent
  frameworks without rebuilding connectivity.
- **One credential to manage.** Your backend authenticates with a single
  application key. No per-user, per-integration secret management in your code.

## How it's different

The design is chosen to keep **you** the relationship, not Vinkius:

- **Write-only credentials.** You can *set* a user's connector secret and *check
  whether it's set* — but it can never be read back, by your code or by the model.
  The raw token never enters your context or your logs.
- **Your users never meet Vinkius.** End-users connect through *your* product;
  Vinkius stays invisible. Your customer relationship is intact.
- **Capabilities are actions, not integrations.** Your agent calls
  `github__create_issue`; Vinkius resolves the auth, permission, protocol, and
  execution. A capability-level failure comes back as a **result**
  (`is_error=True`), not a crash — so your agent loop can feed it back to the
  model and recover gracefully.
- **Stateless, metered execution.** Tool runs go through a per-user runtime
  keyed to a short-lived token that can be killed — billing and revocation are
  per-user, not global.

## Install

```bash
pip install vinkius-connect
```

> **Not yet published?** Or do you want the very latest from `main`? Install
> straight from the repository — no PyPI involved:
>
> ```bash
> pip install "git+https://github.com/VinkiusForDevs/ai-connect-sdk-python.git"
> ```

Requires Python **3.10+** and [`httpx`](https://www.python-httpx.org/) (the only
runtime dependency). The framework adapters are **zero-dependency** — they shape
tools, they never import your framework. Optional extras exist only to install a
framework if you want to build genuine framework objects in tests/examples:
`pip install -e ".[openai]" ".[anthropic]" ".[langchain]"` and friends.

## Quick start

```python
import os
from vinkius_connect import Vinkius

vinkius = Vinkius(
    app_id=os.environ["VINKIUS_APP_ID"],     # vk_app_…  (your tenant)
    api_key=os.environ["VINKIUS_APP_KEY"],   # vk_app_sk_… (your secret, server-side only)
)

# 1. Everything this user can do, as executable tools
capabilities = await vinkius.user("alice_123").capabilities()

# 2. Run one
result = await capabilities.find_capability("github__create_issue").execute(
    {"owner": "acme", "repo": "product", "title": "Ship it"}
)
print(result.text())
```

> Get `app_id` / `api_key` from the [Vinkius Cloud](https://cloud.vinkius.com)
> dashboard (**Build AI Apps → New AI Application → App Keys**). The key is shown
> **once** and is server-side only — never ship it to a browser or the model.

### End-to-end with your framework

The whole loop is: **get the user's capabilities → hand them to your model as
tools → when the model asks for one, execute it and return the result.**

```python
import openai
from vinkius_connect import Vinkius
from vinkius_connect.adapters import openai as vk_openai

client = openai.AsyncOpenAI()
vinkius = Vinkius(app_id=os.environ["VINKIUS_APP_ID"],
                  api_key=os.environ["VINKIUS_APP_KEY"])

caps = await vinkius.user("alice_123").capabilities()

resp = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Open a GitHub issue titled 'Ship it'"}],
    tools=vk_openai.to_openai_tools(caps),        # <- your user's real capabilities
)

call = resp.choices[0].message.tool_calls[0]
if call:
    result = await vk_openai.run_openai_tool_call(caps, call)   # executes on Vinkius
    print(result.text())
```

See [`examples/openai_end_to_end.py`](examples/openai_end_to_end.py) and
[`examples/chatbot.py`](examples/chatbot.py).

## Connect a connector (onboarding a user)

For the first time a user wires up a system, you provision it in a few calls:

```python
github = vinkius.user("alice_123").connector("github")

await github.connect()                                  # get-or-create the connection
await github.credentials.set({"GITHUB_TOKEN": token})   # write-only: set it, never read it
print(await github.status())   # not_connected | needs_credentials | ready | disabled

await github.capabilities()   # the actions this connector provides
```

Credentials are **write-only**: check the schema and which keys are set — the
SDK never returns the secret values.

## Framework adapters

One set of capabilities, many tool formats. Pick the adapter that matches the
stack you're already in — inject that framework's own factory where noted, so the
adapters stay dependency-free.

| Framework                        | Module                                | Use |
| -------------------------------- | ------------------------------------- | --- |
| **OpenAI** (chat completions)    | `adapters.openai`      | `to_openai_tools`, `run_openai_tool_call` |
| **Anthropic** (Messages)         | `adapters.anthropic`    | `to_anthropic_tools`, `run_anthropic_tool_use` |
| **Google Gemini**                | `adapters.gemini`       | `to_gemini_tools`, `run_gemini_function_call` |
| **LangChain**                    | `adapters.langchain`    | `to_langchain_tools` (inject `tool`) |
| **LlamaIndex**                   | `adapters.llamaindex`   | `to_llamaindex_tools` (inject factory) |
| **OpenAI Agents** (`openai-agents`) | `adapters.openai_agents` | `to_openai_agents_tools` (inject factory) |
| **CrewAI**                       | `adapters.crewai`       | `to_crewai_tools` (inject `@tool`), `execute_capability_sync` |
| **Any / neutral**                | `adapters.json_schema`  | `to_json_schema_tools`, `execute_by_name` |

```python
from vinkius_connect.adapters import openai, anthropic, gemini, json_schema

caps = await vinkius.user("alice_123").capabilities()

openai_tools    = openai.to_openai_tools(caps)       # -> tools=[...]
anthropic_tools = anthropic.to_anthropic_tools(caps)  # -> tools=[...]
gemini_decls    = gemini.to_gemini_tools(caps)        # -> functionDeclarations
plain           = json_schema.to_json_schema_tools(caps)  # -> {name, description, parameters}
```

## The mental model

| Term | What it is |
| ---- | ---------- |
| **Connector** | An external system a user connected (GitHub, Slack, …). Provides access. |
| **Capability** | An actionable unit a connector exposes (`list repositories`, `create issue`). Provides action. |
| **User** | Identified by **your** `external_id` (`"alice_123"`). No Vinkius user id to resolve, cache, or store. |
| **Control plane** | Provisioning & state: users, connectors, credentials, catalog (plain REST). |
| **Execution plane** | Runtime: listing & executing capabilities, metered per user by a short-lived token. |

`user.capabilities()` is a **fan-out**: it lists every one of the user's
*ready* connectors in parallel (capped at 8 at a time). One flaky connector
doesn't sink the batch — pass `{"on_connector_error": fn}` to observe failures;
if *all* fail, the first error is raised.

## Reference

### Configuration

```python
Vinkius(
    app_id="vk_app_…",
    api_key="vk_app_sk_…",
    base_url="https://api.vinkius.com",   # default
    timeout_ms=30_000,                    # default
    max_retries=2,                        # default — idempotent requests only
    client=None,                          # inject an httpx.AsyncClient (tests / edge)
    user_agent="acme-ai/1.0",            # appended to the SDK's User-Agent
    namespace_capability=lambda c, n: f"{c}__{n}",
    hooks=None,                           # observability hooks (headers/body redacted)
)
```

Injecting a `client` is the whole testing story: hand it a fake and drive the SDK
offline. Otherwise the SDK owns an `httpx.AsyncClient` — `await vinkius.aclose()`
or `async with Vinkius(...) as v:` to release it.

**Retries:** transient statuses (429/502/503/504) and network errors are retried
with full-jitter backoff **only for retry-safe requests** — idempotent methods
and anything with an `idempotency_key`. A non-idempotent POST (e.g. minting a
connection token) is never auto-retried.

### Low-level API

Every fluent call has a REST equivalent if you want full control:

```python
connection = await vinkius.users.connections("alice_123").create({"connector": "github"})
await vinkius.users.connections("alice_123").credentials(connection["id"]).set(
    {"credentials": {"GITHUB_TOKEN": "…"}}   # low-level uses the HTTP envelope
)

await vinkius.catalog.search("github")        # marketplace-ranked discovery
async for c in vinkius.catalog.iterate(): ...
```

### Errors

Every failure is a `VinkiusError` subclass with `status`, a stable `code`, and the
server `request_id`:

`ConfigError` · `AuthError` · `NotFoundError` · `ValidationError` · `RateLimitError` ·
`QuotaError` · `OverageError` · `ConnectorNotConnectedError` · `ConnectionError` ·
`ProtocolError`

```python
from vinkius_connect import VinkiusError, RateLimitError

try:
    await vinkius.user("alice_123").capabilities()
except RateLimitError as e:
    ...  # e.retry_after_ms
except VinkiusError as e:
    ...  # e.code, e.status, e.request_id, e.details
```

Capability execution **returns** `is_error=True` results instead of throwing, so
your agent can recover; only transport/config/protocol failures raise.

### Security

- **One secret** — `vk_app_sk_*`, server-side only.
- **Identity on every request** — each call carries your app id, validated against
  the key; a key can only ever act for its own app.
- **Write-only credentials** — set, never read back; the model never sees raw secrets.
- **Bounded token exposure** — the `vk_live_*` runtime token + its URL are returned
  only at issue time; the SDK caches *no* secrets, and redacts them before any
  observability hook runs.

## Development

```bash
pip install -e ".[test]"
pytest            # 94 tests, fully offline via an injectable fake transport
```

This is the Python port of the TypeScript SDK (`@vinkius/connect`); both expose
the same contract.

## License

[Apache 2.0](./LICENSE) © Vinkius
