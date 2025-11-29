"""API client for EPB."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional, TypedDict, cast

from aiohttp import ClientError, ClientSession
from multidict import CIMultiDict

_LOGGER = logging.getLogger(__name__)


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


class EPBApiClient:
    """API Client for EPB (Electric Power Board).

    This client handles authentication and data fetching from the EPB API.
    It manages token refresh and provides methods to get account and usage data.
    """

    def __init__(self, username: str, password: str, session: ClientSession) -> None:
        """Initialize the EPB API client.

        Args:
            username: The EPB account username
            password: The EPB account password
            session: The aiohttp client session to use for requests
        """
        self._username = username
        self._password = password
        self._session = session
        self._token: Optional[str] = None
        self.base_url = "https://api.epb.com"
        _LOGGER.debug("Initializing EPB API client for user: %s", username)

    def _get_auth_headers(self) -> CIMultiDict[str]:
        """Get headers for authenticated requests."""
        headers: CIMultiDict[str] = CIMultiDict()
        if self._token:
            headers["X-User-Token"] = self._token
        return headers

    async def authenticate(self) -> None:
        """Authenticate with EPB API.

        Raises:
            EPBAuthError: If authentication fails
            EPBApiError: If there is an API error
        """
        auth_url = f"{self.base_url}/web/api/v1/login/"
        _LOGGER.info("Authenticating with EPB API at %s", auth_url)

        auth_data = {
            "username": self._username,
            "password": self._password,
            "grant_type": "PASSWORD",
        }

        try:
            async with self._session.post(auth_url, json=auth_data) as response:
                _LOGGER.debug("Auth response status: %s", response.status)
                text = await response.text()
                _LOGGER.debug("Auth response: %s", text)

                if response.status != 200:
                    raise EPBAuthError(
                        f"Authentication failed with status {response.status}: {text}"
                    )

                json_response = await response.json()
                self._token = (
                    json_response.get("tokens", {}).get("access", {}).get("token")
                )

                if not self._token:
                    raise EPBAuthError("No token in authentication response")

                _LOGGER.info("Successfully authenticated with EPB API")

        except ClientError as err:
            raise EPBApiError(f"Connection error during authentication: {err}") from err

    async def _ensure_token(self) -> None:
        """Ensure we have a valid token.

        Authenticates if no token is present.
        """
        if not self._token:
            await self.authenticate()

    async def get_account_links(self) -> list[AccountLink]:
        """Get account links from the EPB API.

        Returns:
            A list of account link dictionaries containing account and premise
            information

        Raises:
            EPBAuthError: If authentication fails
            EPBApiError: If there is an API error
        """
        await self._ensure_token()

        url = f"{self.base_url}/web/api/v1/account-links/"
        _LOGGER.debug("Fetching account links from %s", url)

        try:
            async with self._session.get(
                url, headers=self._get_auth_headers()
            ) as response:
                _LOGGER.debug("Account links response status: %s", response.status)
                text = await response.text()
                _LOGGER.debug("Account links response: %s", text)

                if response.status == 400 and "TOKEN_EXPIRED" in text:
                    _LOGGER.info("Token expired, refreshing...")
                    self._token = None
                    await self._ensure_token()
                    return await self.get_account_links()

                if response.status != 200:
                    raise EPBApiError(f"Failed to get account links: {text}")

                data = await response.json()
                return cast(list[AccountLink], data)

        except ClientError as err:
            raise EPBApiError(
                f"Connection error fetching account links: {err}"
            ) from err
        except Exception as err:
            raise EPBApiError(f"Error fetching account links: {err}") from err

    def _extract_usage_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract usage data from API response.

        Args:
            data: The raw API response data

        Returns:
            A dictionary containing:
            - kwh: Month-to-date total kWh (for TOTAL_INCREASING sensor)
            - cost: Month-to-date total cost (for TOTAL_INCREASING sensor)
            - daily_kwh: Today's kWh usage (for daily tracking)
            - daily_cost: Today's cost (for daily tracking)
        """
        result: Dict[str, Any] = {
            "kwh": 0.0,
            "cost": 0.0,
            "daily_kwh": 0.0,
            "daily_cost": 0.0,
        }

        try:
            # Get month-to-date totals (primary data for Energy Dashboard)
            if "interval_a_totals" in data:
                totals = data["interval_a_totals"]
                result["kwh"] = float(totals.get("pos_kwh", 0))
                result["cost"] = float(totals.get("pos_wh_est_cost", 0))
                _LOGGER.debug(
                    "Month-to-date totals: %s kWh, $%s",
                    result["kwh"],
                    result["cost"],
                )

            # Get today's daily usage from the data array
            if "data" in data and data["data"]:
                daily_data = data["data"]
                # Find the last entry that has actual data (today or most recent)
                for entry in reversed(daily_data):
                    if "a" in entry and "values" in entry["a"]:
                        daily_values = entry["a"]["values"]
                        result["daily_kwh"] = float(daily_values.get("pos_kwh", 0))
                        result["daily_cost"] = float(daily_values.get("pos_wh_est_cost", 0))
                        _LOGGER.debug(
                            "Daily usage: %s kWh, $%s",
                            result["daily_kwh"],
                            result["daily_cost"],
                        )
                        break

            # Fallback: if no totals but we have daily data, use daily as totals
            if result["kwh"] == 0.0 and result["daily_kwh"] > 0:
                result["kwh"] = result["daily_kwh"]
                result["cost"] = result["daily_cost"]
                _LOGGER.warning("No totals found, using daily values as fallback")

            if result["kwh"] == 0.0 and result["daily_kwh"] == 0.0:
                _LOGGER.warning("No valid data found in response")

            return result

        except (KeyError, IndexError, TypeError, ValueError) as err:
            _LOGGER.error("Error parsing usage data: %s. Data: %s", err, data)
            return result

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
        await self._ensure_token()

        url = f"{self.base_url}/web/api/v1/usage/power/permanent/compare/daily"
        _LOGGER.debug("Fetching usage data from %s", url)

        # Get current date
        date = datetime.now()
        usage_year = date.year
        usage_month = date.month

        payload = {
            "account_number": account_id,
            "gis_id": gis_id,
            "zone_id": "America/New_York",
            "usage_year": usage_year,
            "usage_month": usage_month,
        }

        _LOGGER.debug("Usage data payload: %s", payload)

        try:
            async with self._session.post(
                url, json=payload, headers=self._get_auth_headers()
            ) as response:
                _LOGGER.debug("Usage data response status: %s", response.status)
                text = await response.text()
                _LOGGER.debug("Usage data response: %s", text)

                if response.status == 400 and "TOKEN_EXPIRED" in text:
                    _LOGGER.info("Token expired, refreshing...")
                    self._token = None
                    await self._ensure_token()
                    return await self.get_usage_data(account_id, gis_id)

                if response.status != 200:
                    raise EPBApiError(f"Failed to get usage data: {text}")

                data = await response.json()
                return self._extract_usage_data(data)

        except ClientError as err:
            raise EPBApiError(f"Connection error fetching usage data: {err}") from err
        except Exception as err:
            _LOGGER.error(
                "Error getting usage data for account %s: %s",
                account_id,
                err,
            )
            return {"kwh": 0.0, "cost": 0.0, "daily_kwh": 0.0, "daily_cost": 0.0}
