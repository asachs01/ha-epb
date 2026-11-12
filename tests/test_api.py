"""Test the EPB API client."""

import base64
import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from aiohttp import ClientError, ClientSession

from custom_components.epb.api import (AccountLink, EPBApiClient, EPBApiError,
                                       EPBAuthError, EPBRateLimitError,
                                       _parse_expiry)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock aiohttp session."""
    session = AsyncMock(spec=ClientSession)
    # Create a new AsyncMock for the context manager
    mock_context = AsyncMock()
    # Configure the context manager's enter and exit
    session.get.return_value.__aenter__ = mock_context.__aenter__
    session.get.return_value.__aexit__ = mock_context.__aexit__
    session.post.return_value.__aenter__ = mock_context.__aenter__
    session.post.return_value.__aexit__ = mock_context.__aexit__
    return session


async def test_authentication_success(mock_session: AsyncMock) -> None:
    """Test successful authentication."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text.return_value = '{"tokens": {"access": {"token": "test-token"}}}'
    mock_response.json.return_value = {"tokens": {"access": {"token": "test-token"}}}

    mock_session.post.return_value.__aenter__.return_value = mock_response

    client = EPBApiClient("test@example.com", "password", mock_session)
    await client.authenticate()

    assert client._token == "test-token"
    mock_session.post.assert_called_once()


async def test_authentication_failure(mock_session: AsyncMock) -> None:
    """Test failed authentication."""
    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.text.return_value = "Invalid credentials"

    mock_session.post.return_value.__aenter__.return_value = mock_response

    client = EPBApiClient("test@example.com", "password", mock_session)

    with pytest.raises(EPBAuthError):
        await client.authenticate()


async def test_get_account_links_success(mock_session: AsyncMock) -> None:
    """Test successful account links retrieval."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = [
        {"power_account": {"account_id": "123", "gis_id": None}}
    ]

    mock_session.get.return_value.__aenter__.return_value = mock_response

    client = EPBApiClient("test@example.com", "password", mock_session)
    client._token = "test-token"

    result = await client.get_account_links()

    assert result == [{"power_account": {"account_id": "123", "gis_id": None}}]
    mock_session.get.assert_called_once()


async def test_get_usage_data_success(mock_session: AsyncMock) -> None:
    """Test successful usage data retrieval."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "interval_a_totals": {"pos_kwh": "500", "pos_wh_est_cost": "62.50"},
        "data": [{"a": {"values": {"pos_kwh": "100", "pos_wh_est_cost": "12.34"}}}],
    }

    mock_session.post.return_value.__aenter__.return_value = mock_response

    client = EPBApiClient("test@example.com", "password", mock_session)
    client._token = "test-token"

    result = await client.get_usage_data("123", "456")

    # Now returns both totals and daily values
    assert result["kwh"] == 500.0  # Month-to-date total
    assert result["cost"] == 62.50  # Month-to-date cost
    assert result["daily_kwh"] == 100.0  # Today's usage
    assert result["daily_cost"] == 12.34  # Today's cost
    mock_session.post.assert_called_once()


async def test_get_usage_data_missing_totals_returns_none(
    mock_session: AsyncMock,
) -> None:
    """Missing totals must yield None, not 0.0, to avoid phantom resets."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {"data": []}

    mock_session.post.return_value.__aenter__.return_value = mock_response

    client = EPBApiClient("test@example.com", "password", mock_session)
    client._token = "test-token"

    result = await client.get_usage_data("123", "456")

    assert result["kwh"] is None
    assert result["cost"] is None
    assert result["daily_kwh"] is None
    assert result["daily_cost"] is None


async def test_get_usage_data_http_error_raises(mock_session: AsyncMock) -> None:
    """Non-200 responses must raise so the coordinator can mark UpdateFailed."""
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.text.return_value = "boom"

    mock_session.post.return_value.__aenter__.return_value = mock_response

    client = EPBApiClient("test@example.com", "password", mock_session)
    client._token = "test-token"

    with pytest.raises(EPBApiError):
        await client.get_usage_data("123", "456")


# ---------------------------------------------------------------------------
# Refresh-token authentication
# ---------------------------------------------------------------------------


def _response(status: int, body: Any = None) -> AsyncMock:
    """Build a mock aiohttp response."""
    response = AsyncMock()
    response.status = status
    response.text.return_value = body if isinstance(body, str) else json.dumps(body)
    response.json.return_value = body
    return response


def _session(*responses: AsyncMock) -> Mock:
    """Mock session whose get/post calls return ``responses`` in order."""
    queue = list(responses)
    session = Mock(spec=ClientSession)

    def _call(*args: Any, **kwargs: Any) -> AsyncMock:
        ctx = AsyncMock()
        ctx.__aenter__.return_value = queue.pop(0)
        return ctx

    session.post.side_effect = _call
    session.get.side_effect = _call
    return session


def _token_body(access: str = "access-1", refresh: str = "refresh-1") -> dict:
    """EPB v2 login response."""
    return {
        "access": {"token": access, "lifetime": 900},
        "refresh": {"token": refresh, "lifetime": 3600},
    }


def _grant_types(session: Mock) -> list[str]:
    """grant_type of every request sent to the login endpoint."""
    return [
        call.kwargs["json"]["grant_type"]
        for call in session.post.call_args_list
        if "/login/" in call.args[0]
    ]


USAGE_BODY = {"interval_a_totals": {"pos_kwh": "500", "pos_wh_est_cost": "62.50"}}


async def test_password_login_stores_refresh_token_and_persists() -> None:
    """A password login keeps both tokens and hands them to the callback."""
    session = _session(_response(200, _token_body()))
    saved: list[dict] = []

    async def _save(tokens: dict) -> None:
        saved.append(tokens)

    client = EPBApiClient("user", "pw", session, token_callback=_save)
    await client.authenticate()

    assert session.post.call_args.args[0].endswith("/web/api/v2/login/")
    assert client.tokens["access_token"] == "access-1"
    assert client.tokens["refresh_token"] == "refresh-1"
    assert client.tokens["access_expires_at"] == pytest.approx(time.time() + 900, 5)
    assert client.tokens["refresh_expires_at"] == pytest.approx(time.time() + 3600, 5)
    assert saved == [client.tokens]


async def test_expired_access_token_uses_refresh_token() -> None:
    """An expired access token is renewed with the refresh token, not a login."""
    session = _session(
        _response(200, _token_body("access-2", "refresh-2")),
        _response(200, USAGE_BODY),
    )
    client = EPBApiClient(
        "user",
        "pw",
        session,
        tokens={
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "access_expires_at": time.time() - 10,
            "refresh_expires_at": time.time() + 1800,
        },
    )

    result = await client.get_usage_data("123", 456)

    assert result["kwh"] == 500.0
    assert _grant_types(session) == ["REFRESH_TOKEN"]
    refresh_payload = session.post.call_args_list[0].kwargs["json"]
    assert refresh_payload["refresh_token"] == "refresh-1"
    assert "password" not in refresh_payload
    # Each refresh returns a new refresh token, which must replace the old one.
    assert client.tokens["refresh_token"] == "refresh-2"
    assert session.post.call_args_list[1].kwargs["headers"]["X-User-Token"] == (
        "access-2"
    )


async def test_fresh_saved_tokens_skip_login() -> None:
    """Tokens restored after a restart are used without any login."""
    session = _session(_response(200, USAGE_BODY))
    client = EPBApiClient(
        "user",
        "pw",
        session,
        tokens={
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "access_expires_at": time.time() + 600,
            "refresh_expires_at": time.time() + 3000,
        },
    )

    await client.get_usage_data("123", 456)

    assert _grant_types(session) == []


async def test_rejected_refresh_token_falls_back_to_password() -> None:
    """If EPB rejects the refresh token, a password login is used once."""
    session = _session(
        _response(401, "invalid refresh token"),
        _response(200, _token_body("access-2", "refresh-2")),
        _response(200, USAGE_BODY),
    )
    client = EPBApiClient(
        "user",
        "pw",
        session,
        tokens={
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "access_expires_at": time.time() - 10,
            "refresh_expires_at": time.time() + 1800,
        },
    )

    await client.get_usage_data("123", 456)

    assert _grant_types(session) == ["REFRESH_TOKEN", "PASSWORD"]
    assert client.tokens["refresh_token"] == "refresh-2"


async def test_expired_refresh_token_goes_straight_to_password() -> None:
    """A refresh token past its expiry isn't sent; a password login is used."""
    session = _session(
        _response(200, _token_body("access-2", "refresh-2")),
        _response(200, USAGE_BODY),
    )
    client = EPBApiClient(
        "user",
        "pw",
        session,
        tokens={
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "access_expires_at": time.time() - 3000,
            "refresh_expires_at": time.time() - 10,
        },
    )

    await client.get_usage_data("123", 456)

    assert _grant_types(session) == ["PASSWORD"]


async def test_rate_limited_refresh_does_not_try_password() -> None:
    """A 429 must not be answered with a password login (it would make it worse)."""
    session = _session(_response(429, "Too many requests"))
    client = EPBApiClient(
        "user",
        "pw",
        session,
        tokens={
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "access_expires_at": time.time() - 10,
            "refresh_expires_at": time.time() + 1800,
        },
    )

    with pytest.raises(EPBRateLimitError):
        await client.get_usage_data("123", 456)

    assert _grant_types(session) == ["REFRESH_TOKEN"]


async def test_token_expired_response_renews_and_retries() -> None:
    """A TOKEN_EXPIRED API response renews via refresh token and retries once."""
    session = _session(
        _response(400, '{"error": "TOKEN_EXPIRED"}'),
        _response(200, _token_body("access-2", "refresh-2")),
        _response(200, USAGE_BODY),
    )
    client = EPBApiClient(
        "user",
        "pw",
        session,
        tokens={
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "access_expires_at": time.time() + 600,
            "refresh_expires_at": time.time() + 3000,
        },
    )

    result = await client.get_usage_data("123", 456)

    assert result["kwh"] == 500.0
    assert _grant_types(session) == ["REFRESH_TOKEN"]
    assert session.post.call_args_list[2].kwargs["headers"]["X-User-Token"] == (
        "access-2"
    )


async def test_parse_expiry_variants() -> None:
    """Expiry is read from lifetime, ISO timestamps, or the JWT exp claim."""
    now = time.time()
    assert _parse_expiry({"lifetime": 900}, "x") == pytest.approx(now + 900, 5)

    iso = datetime.fromtimestamp(now + 600, tz=timezone.utc).isoformat()
    assert _parse_expiry({"expires_on": iso}, "x") == pytest.approx(now + 600, 5)

    payload = base64.urlsafe_b64encode(json.dumps({"exp": 1900000000}).encode())
    jwt = f"header.{payload.decode().rstrip('=')}.sig"
    assert _parse_expiry({}, jwt) == 1900000000.0

    assert _parse_expiry({}, "not-a-jwt") is None
