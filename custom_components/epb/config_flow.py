"""Config flow for EPB integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import (CONF_PASSWORD, CONF_SCAN_INTERVAL,
                                 CONF_USERNAME)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client, selector

from .api import EPBApiClient, EPBApiError, EPBAuthError
from .const import CONF_TOKENS, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(
            CONF_SCAN_INTERVAL,
            default=DEFAULT_SCAN_INTERVAL.total_seconds() // 60,
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=55,
                step=1,
                unit_of_measurement="minutes",
                mode=selector.NumberSelectorMode.SLIDER,
            ),
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Returns the tokens from the login so setup can reuse them instead of
    immediately spending a second rate-limited password login.
    """
    session = aiohttp_client.async_get_clientsession(hass)
    client = EPBApiClient(
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        session,
    )

    try:
        await client.authenticate()
    except EPBAuthError as err:
        raise InvalidAuth from err
    except EPBApiError as err:
        raise CannotConnect from err
    return client.tokens


@config_entries.HANDLERS.register(DOMAIN)
class EPBConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for EPB."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EPBOptionsFlow:
        """Get the options flow for this handler."""
        return EPBOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                tokens = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={**user_input, CONF_TOKENS: tokens},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class EPBOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Stored as plain minutes: options must be JSON-serialisable.
            if CONF_SCAN_INTERVAL in user_input:
                user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            return self.async_create_entry(title="", data=user_input)

        # Convert timedelta to minutes for the form
        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        if isinstance(current_interval, timedelta):
            interval_minutes = current_interval.total_seconds() / 60
        else:
            interval_minutes = float(current_interval)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=int(interval_minutes)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=55,
                        step=1,
                        unit_of_measurement="minutes",
                        mode=selector.NumberSelectorMode.SLIDER,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
