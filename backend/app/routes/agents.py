"""Agent connection utility endpoints.

`POST /api/agents/test` — sends a single canned 'ping' message through the
adapter the user is about to use, so the Submit screen can give a green check
before the real run starts.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from ..agents.base import reset_agent_auth_header, set_agent_auth_header
from ..agents.factory import build_adapter
from ..agents.safety import UnsafeEndpointError, assert_endpoint_safe
from ..auth import get_current_user, verify_csrf
from ..models import User
from ..schemas import TestConnectionRequest, TestConnectionResponse

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("/test", response_model=TestConnectionResponse)
def test_connection(
    body: TestConnectionRequest,
    _user: User = Depends(get_current_user),
    _csrf: str = Depends(verify_csrf),
    x_agent_auth_header: str | None = Header(default=None, alias="X-Agent-Auth-Header"),
) -> TestConnectionResponse:
    try:
        assert_endpoint_safe(body.url)
    except UnsafeEndpointError as exc:
        return TestConnectionResponse(ok=False, error=str(exc))

    try:
        adapter = build_adapter(
            connection_type="http_endpoint",
            model=body.model,
            endpoint_url=body.url,
            endpoint_format=body.format,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = (
        set_agent_auth_header(x_agent_auth_header) if x_agent_auth_header else None
    )
    try:
        text, latency = adapter.send(
            [{"role": "user", "content": "ping"}], max_tokens=64
        )
        return TestConnectionResponse(
            ok=True,
            latency_ms=latency,
            sample_response=text[:400],
        )
    except Exception as exc:
        return TestConnectionResponse(ok=False, error=str(exc)[:500])
    finally:
        if token is not None:
            reset_agent_auth_header(token)
