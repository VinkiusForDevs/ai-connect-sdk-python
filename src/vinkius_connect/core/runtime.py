"""RuntimeClient — the ONLY surface for tool listing and execution.

Vinkius meters, bills, and kill-switches every tool call at the runtime, keyed
by the ``vk_live_*`` token embedded in the connection's ``mcp_url`` path. The
API is NEVER an execution surface. This client therefore talks JSON-RPC 2.0 over
Streamable HTTP directly to ``{RUNTIME}/{token}/mcp``, statelessly (one POST, no
``initialize`` handshake, no session id).

Responsibilities:

* ``tools/list`` (free, un-metered) and ``tools/call`` (metered) as single POSTs.
* Retries for the idempotent ``tools/list`` only; ``tools/call`` retries solely
  when the caller supplies an idempotency key (side-effect safety).
* Runtime error mapping: revoked token (403) -> :class:`AuthError`, unknown
  (404) -> :class:`NotFoundError`, transient (5xx) ->
  :class:`~vinkius_connect.core.errors.VinkiusError` (``connection_error``),
  JSON-RPC errors -> :class:`ProtocolError`. Tool-level failures are returned
  as ``{is_error: True}``.
* Redacted observability hooks (the ``vk_live_*`` path segment is masked).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .errors import AuthError, NotFoundError, ProtocolError, VinkiusError
from .retry import RetryPolicy
from .transport import Transport, TransportConfig, TransportRequest
from ..types import CapabilityResult

__all__ = ["RuntimeClient"]

#: JSON-RPC protocol version advertised to the runtime (2026-era stateless).
MCP_PROTOCOL_VERSION = "2026-07-28"


class RuntimeClientConfig:
    def __init__(
        self,
        *,
        timeout_ms: int,
        retry: RetryPolicy,
        client: Any,
        user_agent: str,
        hooks: Optional[Any] = None,
    ) -> None:
        self.timeout_ms = timeout_ms
        self.retry = retry
        self.client = client
        self.user_agent = user_agent
        self.hooks = hooks

    def transport(self) -> Transport:
        return Transport(
            TransportConfig(
                timeout_ms=self.timeout_ms,
                retry=self.retry,
                client=self.client,
                user_agent=self.user_agent,
                hooks=self.hooks,
            )
        )


class RuntimeClient:
    """A stateless JSON-RPC client bound to ONE runtime endpoint (``mcp_url``).

    The ``mcp_url`` already embeds the ``vk_live_*`` token, so no auth headers
    are added here.
    """

    def __init__(self, mcp_url: str, cfg: RuntimeClientConfig) -> None:
        self._mcp_url = mcp_url
        self.cfg = cfg
        self._transport = cfg.transport()
        self._next_id = 1

    async def list_tools(
        self, *, idempotency_key: Optional[str] = None, timeout_ms: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """List the tools this connection exposes. Free (un-metered) at the runtime."""
        result = await self._rpc("tools/list", {}, idempotency_key, timeout_ms, retryable=True)
        tools = (result or {}).get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list):
            raise ProtocolError(
                "Runtime tools/list returned no tools array.", code="protocol_error", details=result
            )
        return [normalize_tool_definition(tool) for tool in tools]

    async def call_tool(
        self,
        name: str,
        args: Optional[dict[str, Any]],
        *,
        idempotency_key: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ) -> CapabilityResult:
        """Execute a tool. Metered against the connection's token."""
        result = await self._rpc(
            "tools/call",
            {"name": name, "arguments": args or {}},
            idempotency_key,
            timeout_ms,
            retryable=idempotency_key is not None,
        )
        return normalize_call_result(result)

    # ── internals ───────────────────────────────────────────────────────

    async def _rpc(
        self,
        method: str,
        params: dict[str, Any],
        idempotency_key: Optional[str],
        timeout_ms: Optional[int],
        *,
        retryable: bool,
    ) -> Any:
        envelope_body = json.dumps(
            {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        )
        self._next_id += 1
        result = await self._transport.send(
            TransportRequest(
                url=self._mcp_url,
                method="POST",
                headers=self._headers(idempotency_key),
                body=envelope_body,
                retryable=retryable,
                label="Runtime request",
                timeout_ms=timeout_ms,
            )
        )
        if not (200 <= result.status < 300):
            raise self._map_runtime_http_error(result.status, result.body)
        return self._unwrap_envelope(result.body)

    def _unwrap_envelope(self, body: Any) -> Any:
        """Extract the JSON-RPC ``result``, or map a JSON-RPC ``error`` object."""
        # The runtime may answer as an SSE stream; take the last data frame.
        envelope = _extract_envelope(body)
        if not isinstance(envelope, dict):
            raise ProtocolError(
                "Runtime returned a non-JSON-RPC response.",
                code="protocol_error",
                details=body,
            )
        rpc_error = envelope.get("error")
        if rpc_error:
            message = rpc_error.get("message") if isinstance(rpc_error, dict) else None
            raise ProtocolError(
                message or "Runtime returned a JSON-RPC error.",
                code="protocol_error",
                details=rpc_error,
            )
        if "result" not in envelope:
            raise ProtocolError(
                "Runtime JSON-RPC response has no result.",
                code="protocol_error",
                details=body,
            )
        return envelope["result"]

    def _headers(self, idempotency_key: Optional[str]) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
            "mcp-protocol-version": MCP_PROTOCOL_VERSION,
            "user-agent": self.cfg.user_agent,
        }
        if idempotency_key:
            headers["idempotency-key"] = idempotency_key
        return headers

    def _map_runtime_http_error(self, status: int, body: Any) -> VinkiusError:
        message = _pick_runtime_message(body, f"Runtime request failed with status {status}")
        base = {"status": status, "details": body}
        if status in (401, 403):
            return AuthError(message, **base)
        if status == 404:
            return NotFoundError(message, **base)
        return VinkiusError(message, code="connection_error", **base)


# ── Normalization ────────────────────────────────────────────────────────────


def normalize_tool_definition(tool: Any) -> dict[str, Any]:
    """Map a raw runtime tool definition (camelCase) to the SDK's CapabilityData."""
    t = tool if isinstance(tool, dict) else {}
    name = t.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ProtocolError(
            "Runtime tool definition is missing a name.", code="protocol_error", details=tool
        )
    out: dict[str, Any] = {
        "name": name,
        "title": t.get("title") if isinstance(t.get("title"), str) else None,
        "description": t.get("description") if isinstance(t.get("description"), str) else None,
        # Runtime uses JSON-Schema `inputSchema` (camelCase); the SDK contract is snake_case.
        "input_schema": t.get("inputSchema", t.get("input_schema", {})),
    }
    if "annotations" in t:
        out["annotations"] = t["annotations"]
    return out


def normalize_call_result(result: Any) -> CapabilityResult:
    """Map a runtime tools/call JSON-RPC result to the SDK's CapabilityResult."""
    r = result if isinstance(result, dict) else {}
    raw_content = r.get("content")
    content = []
    if isinstance(raw_content, list):
        for entry in raw_content:
            if not isinstance(entry, dict):
                continue
            ctype = entry.get("type") if isinstance(entry.get("type"), str) else "text"
            text = entry.get("text") if isinstance(entry.get("text"), str) else json.dumps(entry)
            content.append({"type": ctype, "text": text})
    normalized = CapabilityResult(content=content, is_error=(r.get("isError") is True))
    # The MCP data plane may return a parsed object alongside the textual content.
    # Surface it verbatim when present — never parsed or transformed by the SDK.
    if "structuredContent" in r:
        normalized.structured_content = r["structuredContent"]
    return normalized


def _pick_runtime_message(body: Any, fallback: str) -> str:
    if isinstance(body, dict):
        if isinstance(body.get("error"), str) and body["error"]:
            return body["error"]
        err = body.get("error")
        if isinstance(err, dict) and isinstance(err.get("message"), str):
            return err["message"]
        if isinstance(body.get("message"), str) and body["message"]:
            return body["message"]
    if isinstance(body, str) and body:
        return body
    return fallback


def _extract_envelope(body: Any) -> Any:
    """Accept either a JSON object or an SSE stream string; return the envelope."""
    if not isinstance(body, str):
        return body
    last: Any = None
    for line in body.split("\n"):
        trimmed = line.strip()
        # The SSE spec allows `data:` with OR without a following space.
        if trimmed.startswith("data:"):
            payload_text = trimmed[5:].lstrip()
            try:
                payload = json.loads(payload_text)
            except (ValueError, TypeError):
                continue  # ignore non-JSON SSE frames (comments, keep-alives)
            if isinstance(payload, dict):
                last = payload
    return body if last is None else last
