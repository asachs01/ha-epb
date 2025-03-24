"""Data update coordinator for EPB integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AccountLink, EPBApiClient, EPBApiError, EPBAuthError

_LOGGER = logging.getLogger(__name__)


class EPBUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching EPB data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EPBApiClient,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="EPB",
            update_interval=update_interval,
        )
        self.client = client
        self.account_links: list[AccountLink] = []
        # Track previous KWH values and accumulated totals
        self._prev_kwh_values: Dict[str, float] = {}
        self._accumulated_kwh: Dict[str, float] = {}
        self._last_hour: Dict[str, int] = {}
        self._current_day: int = datetime.now().day

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from EPB."""
        try:
            if not self.account_links:
                self.account_links = await self.client.get_account_links()

            data: Dict[str, Any] = {}
            current_time = datetime.now()
            current_hour = current_time.hour
            current_day = current_time.day

            # Check if we've moved to a new day, reset accumulated values if so
            if current_day != self._current_day:
                _LOGGER.info("New day detected, resetting accumulated KWH values")
                self._accumulated_kwh = {}
                self._current_day = current_day

            for account in self.account_links:
                account_id = account["power_account"]["account_id"]
                gis_id = account.get("premise", {}).get("gis_id")

                if account_id:
                    # Get raw usage data from API
                    raw_usage_data = await self.client.get_usage_data(
                        account_id, gis_id
                    )

                    # Process KWH value to handle hourly resets
                    current_kwh = raw_usage_data.get("kwh", 0.0)

                    # Initialize tracking for this account if not already done
                    if account_id not in self._prev_kwh_values:
                        self._prev_kwh_values[account_id] = current_kwh
                        self._accumulated_kwh[account_id] = 0.0
                        self._last_hour[account_id] = current_hour

                    # Check if we've moved to a new hour since the last update
                    if current_hour != self._last_hour[account_id]:
                        _LOGGER.debug(
                            "Hour change detected for account %s: %s -> %s",
                            account_id,
                            self._last_hour[account_id],
                            current_hour,
                        )

                        # Check for reset: current < previous
                        # Check if difference is significant
                        prev_kwh = self._prev_kwh_values[account_id]
                        if current_kwh < prev_kwh and prev_kwh > 0.1:  # Non-zero check

                            # Calculate the percentage drop
                            percentage_drop = 1.0 - (current_kwh / prev_kwh)

                            # If drop is significant (> 50%), consider it a reset
                            if percentage_drop > 0.5:
                                _LOGGER.info(
                                    "KWH reset detected for account %s: previous=%f, "
                                    "current=%f, drop=%.1f%%",
                                    account_id,
                                    prev_kwh,
                                    current_kwh,
                                    percentage_drop * 100,
                                )
                                # Add the last value before reset to accumulated total
                                self._accumulated_kwh[account_id] += prev_kwh

                        # Update last hour regardless of reset detection
                        self._last_hour[account_id] = current_hour

                    # Calculate total KWH (accumulated + current)
                    total_kwh = self._accumulated_kwh[account_id] + current_kwh

                    # Update previous value for next comparison
                    self._prev_kwh_values[account_id] = current_kwh

                    # Create the data entry with both raw and accumulated values
                    data[account_id] = {
                        "kwh": total_kwh,
                        "raw_kwh": current_kwh,  # Keep the raw value for reference
                        "cost": raw_usage_data.get("cost", 0.0),
                    }

                    _LOGGER.debug(
                        "Account %s: raw_kwh=%f, accumulated=%f, total=%f",
                        account_id,
                        current_kwh,
                        self._accumulated_kwh[account_id],
                        total_kwh,
                    )

            return data

        except EPBAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except EPBApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
