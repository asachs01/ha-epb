"""API client for EPB."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional, TypedDict, cast

from aiohttp import ClientError, ClientSession
from multidict import CIMultiDict

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://api.epb.com"
# v1 login is deprecated by EPB; v2 is what epb.com itself uses.
LOGIN_PATH = "/web/api/v2/login/"

# Renew the access token this many seconds before its stated expiry.
EXPIRY_MARGIN_SECONDS = 120
# Don't attempt a refresh with a refresh token this close to its expiry.
REFRESH_MARGIN_SECONDS = 30

# Called with the current token dict whenever tokens change, so they can be
# persisted and reused across Home Assistant restarts / reloads.
TokenCallback = Callable[[Dict[str, Any]], Awaitable[None]]

_EMPTY_USAGE: Dict[str, Optional[float]] = {
    "kwh": None,
    "cost": None,
    "daily_kwh": None,
    "daily_cost": None,
}


class PowerAccount(TypedDict):
    """Type for power account data."""

    account_id: str
    nickname: str
    status: str


class Premise(TypedDict):
    """Type for premise data."""

    city: str
    full_service_address: str
    gis_id: int
    label: str
    state: str
    zip_code: str
    zone_id: str


class AccountLink(TypedDict):
    """Type for account link data."""

    power_account: PowerAccount
    premise: Premise


class EPBApiError(Exception):
    """Base exception for EPB API errors."""


class EPBAuthError(EPBApiError):
    """Authentication error from EPB API."""


class EPBRateLimitError(EPBApiError):
    """EPB rejected the request because of login rate limiting."""


def _jwt_exp(token: str) -> Optional[float]:
    """Return the ``exp`` claim of a JWT, or None if it isn't a JWT."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp")
        return float(exp) if exp else None
    except (IndexError, ValueError, TypeError, AttributeError):
        return None


def _parse_expiry(token_info: Dict[str, Any], token: str) -> Optional[float]:
    """Work out when an access token expires, as a Unix timestamp.

    The exact shape of EPB's token response isn't documented, so this accepts
    the common variants and falls back to decoding the token as a JWT. If
    nothing works, None is returned and expiry is handled reactively when the
    API reports TOKEN_EXPIRED.
    """
    # EPB v2 returns "lifetime" (seconds) and "expires_on" (ISO timestamp).
    # A relative lifetime is preferred because it is immune to clock skew.
    for key in ("lifetime", "expires_in", "expiresIn"):
        value = token_info.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return time.time() + float(value)

    for key in (
        "expires_on",
        "expires_at",
        "expiresAt",
        "expiration",
        "expires",
        "exp",
    ):
        value = token_info.get(key)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            # Milliseconds vs seconds
            return float(value) / 1000 if value > 1e12 else float(value)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                pass

    return _jwt_exp(token)


class EPBApiClient:
    """API Client for EPB (Electric Power Board).

    Authentication strategy (EPB allows only 6 password logins per 15 minutes
    and 12 per 24 hours):

    1. Reuse the stored access token while it is valid.
    2. When it expires, exchange the refresh token for a new access token
       (grant_type REFRESH_TOKEN) - this does not count as a password login.
    3. Only fall back to a password login when there is no refresh token or
       the refresh token itself has been rejected.
    """

    def __init__(
        self,
        username: str,
        password: str,
        session: ClientSession,
        tokens: Optional[Dict[str, Any]] = None,
        token_callback: Optional[TokenCallback] = None,
    ) -> None:
        """Initialize the EPB API client.

        Args:
            username: The EPB account username
            password: The EPB account password
            session: The aiohttp client session to use for requests
            tokens: Previously saved tokens (see ``tokens`` property)
            token_callback: Awaited with the new tokens whenever they change
        """
        self._username = username
        self._password = password
        self._session = session
        self._token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None
        self._refresh_expires_at: Optional[float] = None
        self._token_callback = token_callback
        self._auth_lock = asyncio.Lock()
        self.base_url = BASE_URL
        if tokens:
            self.load_tokens(tokens)
        _LOGGER.debug("Initializing EPB API client for user: %s", username)

    # ------------------------------------------------------------------
    # Token handling
    # ------------------------------------------------------------------

    @property
    def tokens(self) -> Dict[str, Any]:
        """Current tokens in a form suitable for persisting."""
        return {
            "access_token": self._token,
            "refresh_token": self._refresh_token,
            "access_expires_at": self._token_expires_at,
            "refresh_expires_at": self._refresh_expires_at,
        }

    def load_tokens(self, tokens: Dict[str, Any]) -> None:
        """Restore previously saved tokens."""
        self._token = tokens.get("access_token")
        self._refresh_token = tokens.get("refresh_token")
        self._token_expires_at = tokens.get("access_expires_at")
        self._refresh_expires_at = tokens.get("refresh_expires_at")

    def _refresh_token_usable(self) -> bool:
        if not self._refresh_token:
            return False
        if self._refresh_expires_at is None:
            return True
        return time.time() < self._refresh_expires_at - REFRESH_MARGIN_SECONDS

    def _token_is_fresh(self) -> bool:
        if not self._token:
            return False
        if self._token_expires_at is None:
            # Unknown lifetime: use it until the API says it has expired.
            return True
        return time.time() < self._token_expires_at - EXPIRY_MARGIN_SECONDS

    def _get_auth_headers(self) -> CIMultiDict[str]:
        """Get headers for authenticated requests."""
        headers: CIMultiDict[str] = CIMultiDict()
        if self._token:
            headers["X-User-Token"] = self._token
        return headers

    async def _token_request(self, payload: Dict[str, Any], kind: str) -> None:
        """POST to the login endpoint and store the returned tokens."""
        auth_url = f"{self.base_url}{LOGIN_PATH}"
        _LOGGER.debug("Requesting EPB token (%s) from %s", kind, auth_url)

        try:
            async with self._session.post(auth_url, json=payload) as response:
                text = await response.text()
                _LOGGER.debug("Token (%s) response status: %s", kind, response.status)

                if response.status == 429:
                    raise EPBRateLimitError(
                        f"EPB rate limited the {kind} login (HTTP 429): {text}"
                    )
                if response.status != 200:
                    raise EPBAuthError(
                        f"{kind} login failed with status {response.status}: {text}"
                    )

                json_response = await response.json()
        except ClientError as err:
            raise EPBApiError(f"Connection error during {kind} login: {err}") from err

        json_response = json_response or {}
        # v2 puts "access"/"refresh" at the top level; v1 nested them in "tokens".
        tokens = json_response.get("tokens") or json_response
        access = tokens.get("access") or {}
        access_token = access.get("token") if isinstance(access, dict) else access
        if not access_token:
            raise EPBAuthError(f"No access token in {kind} login response")

        refresh = tokens.get("refresh") or {}
        refresh_token = refresh.get("token") if isinstance(refresh, dict) else refresh

        self._token = access_token
        if refresh_token:
            self._refresh_token = refresh_token
            self._refresh_expires_at = _parse_expiry(
                refresh if isinstance(refresh, dict) else {}, refresh_token
            )
        elif kind == "refresh":
            _LOGGER.debug("Refresh response did not include a new refresh token")
        else:
            _LOGGER.warning(
                "EPB login response contained no refresh token; every token "
                "expiry will require a password login"
            )
        self._token_expires_at = _parse_expiry(
            access if isinstance(access, dict) else {}, access_token
        )

        now = time.time()
        _LOGGER.debug(
            "EPB tokens (%s): access valid %ss, refresh valid %ss, "
            "new refresh token: %s",
            kind,
            round(self._token_expires_at - now) if self._token_expires_at else "?",
            round(self._refresh_expires_at - now) if self._refresh_expires_at else "?",
            bool(refresh_token),
        )

        if self._token_callback:
            try:
                await self._token_callback(self.tokens)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Failed to persist EPB tokens")

    async def authenticate(self) -> None:
        """Log in with username and password (counts against rate limit).

        Raises:
            EPBAuthError: If authentication fails
            EPBRateLimitError: If EPB is rate limiting logins
            EPBApiError: If there is an API error
        """
        _LOGGER.info("Logging in to EPB with password")
        await self._token_request(
            {
                "grant_type": "PASSWORD",
                "username": self._username,
                "password": self._password,
            },
            "password",
        )
        _LOGGER.info("Successfully authenticated with EPB API")

    async def refresh_access_token(self) -> None:
        """Get a new access token using the refresh token.

        Raises:
            EPBAuthError: If there is no refresh token or it was rejected
            EPBRateLimitError: If EPB is rate limiting logins
            EPBApiError: If there is an API error
        """
        if not self._refresh_token:
            raise EPBAuthError("No refresh token available")
        await self._token_request(
            {
                "grant_type": "REFRESH_TOKEN",
                "username": self._username,
                "refresh_token": self._refresh_token,
            },
            "refresh",
        )
        _LOGGER.debug("Refreshed EPB access token")

    async def _renew_token(self) -> None:
        """Obtain a new access token, preferring the refresh token."""
        if self._refresh_token and not self._refresh_token_usable():
            _LOGGER.info("EPB refresh token has expired; password login required")
            self._refresh_token = None
        if self._refresh_token:
            try:
                await self.refresh_access_token()
                return
            except EPBRateLimitError:
                raise
            except EPBAuthError as err:
                _LOGGER.warning(
                    "EPB refresh token rejected (%s); falling back to password login",
                    err,
                )
                self._refresh_token = None
        await self.authenticate()

    async def _ensure_token(self) -> None:
        """Make sure a usable access token is available."""
        async with self._auth_lock:
            if not self._token_is_fresh():
                await self._renew_token()

    async def _handle_token_rejected(self, rejected_token: Optional[str]) -> None:
        async with self._auth_lock:
            # Another caller may already have renewed it.
            if self._token and self._token != rejected_token:
                return
            self._token = None
            self._token_expires_at = None
            await self._renew_token()

    @staticmethod
    def _is_token_rejected(status: int, text: str) -> bool:
        if status == 401:
            return True
        return (
            status in (400, 403)
            and isinstance(text, str)
            and ("TOKEN_EXPIRED" in text or "TOKEN_INVALID" in text)
        )

    async def _api_request(
        self, method: str, url: str, payload: Optional[Dict[str, Any]], what: str
    ) -> Any:
        """Make an authenticated request, renewing the token once if rejected."""
        await self._ensure_token()

        for attempt in (1, 2):
            call = self._session.get if method == "GET" else self._session.post
            kwargs: Dict[str, Any] = {"headers": self._get_auth_headers()}
            if payload is not None:
                kwargs["json"] = payload
            sent_token = self._token

            try:
                async with call(url, **kwargs) as response:
                    text = await response.text()
                    _LOGGER.debug("%s response status: %s", what, response.status)
                    _LOGGER.debug("%s response: %s", what, text)

                    if attempt == 1 and self._is_token_rejected(response.status, text):
                        _LOGGER.info("EPB access token rejected, renewing")
                        await self._handle_token_rejected(sent_token)
                        continue

                    if response.status == 429:
                        raise EPBRateLimitError(f"{what} rate limited: {text}")
                    if response.status != 200:
                        raise EPBApiError(
                            f"Failed to get {what} (status {response.status}): {text}"
                        )

                    return await response.json()
            except EPBApiError:
                raise
            except ClientError as err:
                raise EPBApiError(f"Connection error fetching {what}: {err}") from err
            except Exception as err:
                raise EPBApiError(f"Error fetching {what}: {err}") from err

        raise EPBAuthError(f"EPB rejected a freshly issued token fetching {what}")

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    async def get_account_links(self) -> list[AccountLink]:
        """Get account links from the EPB API.

        Returns:
            A list of account link dictionaries containing account and premise
            information

        Raises:
            EPBAuthError: If authentication fails
            EPBApiError: If there is an API error
        """
        url = f"{self.base_url}/web/api/v1/account-links/"
        data = await self._api_request("GET", url, None, "account links")
        return cast(list[AccountLink], data)

    def _extract_usage_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract usage data from API response.

        Args:
            data: The raw API response data

        Returns:
            A dictionary containing:
            - kwh: Month-to-date total kWh, or None if missing
            - cost: Month-to-date total cost, or None if missing
            - daily_kwh: Today's kWh usage, or None if missing
            - daily_cost: Today's cost, or None if missing

        None is used (rather than 0.0) so sensors report ``unavailable``
        on transient parse failures instead of a synthetic zero, which
        a TOTAL_INCREASING sensor would treat as a meter reset.
        """
        result: Dict[str, Any] = dict(_EMPTY_USAGE)

        try:
            totals = data.get("interval_a_totals") or {}
            if "pos_kwh" in totals:
                result["kwh"] = float(totals["pos_kwh"])
            if "pos_wh_est_cost" in totals:
                result["cost"] = float(totals["pos_wh_est_cost"])

            for entry in reversed(data.get("data") or []):
                values = entry.get("a", {}).get("values")
                if not values:
                    continue
                if "pos_kwh" in values:
                    result["daily_kwh"] = float(values["pos_kwh"])
                if "pos_wh_est_cost" in values:
                    result["daily_cost"] = float(values["pos_wh_est_cost"])
                break

            _LOGGER.debug("Parsed usage: %s", result)

            if result["kwh"] is None and result["daily_kwh"] is None:
                _LOGGER.warning("No valid data found in response: %s", data)

            return result

        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as err:
            _LOGGER.error("Error parsing usage data: %s. Data: %s", err, data)
            return dict(_EMPTY_USAGE)

    async def get_usage_data(
        self, account_id: str, gis_id: Optional[int]
    ) -> Dict[str, Any]:
        """Get usage data for an account.

        Args:
            account_id: The EPB account ID
            gis_id: The optional GIS ID for the account

        Returns:
            A dictionary containing kwh and cost values

        Raises:
            EPBAuthError: If authentication fails
            EPBApiError: If there is an API error
        """
        url = f"{self.base_url}/web/api/v1/usage/power/permanent/compare/daily"

        date = datetime.now()
        payload = {
            "account_number": account_id,
            "gis_id": gis_id,
            "zone_id": "America/New_York",
            "usage_year": date.year,
            "usage_month": date.month,
        }
        _LOGGER.debug("Usage data payload: %s", payload)

        data = await self._api_request("POST", url, payload, "usage data")
        return self._extract_usage_data(data)
