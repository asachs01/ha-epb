"""The EPB integration.

This integration provides support for monitoring EPB (Electric Power Board) power usage
and cost.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_PASSWORD, CONF_SCAN_INTERVAL,
                                 CONF_USERNAME, Platform)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .api import EPBApiClient
from .const import CONF_TOKENS, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import EPBUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
STORAGE_VERSION = 1

# This integration only supports config entries
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the EPB component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EPB from a config entry."""
    session = async_get_clientsession(hass)

    # Tokens live in a separate Store rather than entry.data: updating
    # entry.data would fire the update listener and reload the entry on every
    # token refresh. This lets restarts and reloads reuse the existing
    # access/refresh tokens instead of spending a rate-limited password login.
    store: Store[dict] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
    tokens = await store.async_load() or entry.data.get(CONF_TOKENS)

    async def _save_tokens(new_tokens: dict) -> None:
        await store.async_save(new_tokens)

    client = EPBApiClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session,
        tokens=tokens,
        token_callback=_save_tokens,
    )

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    if isinstance(scan_interval, (int, float)):
        scan_interval = timedelta(minutes=scan_interval)
    # EPB refresh tokens last 60 minutes and each poll renews them, so polling
    # less often than that would force a rate-limited password login.
    scan_interval = min(scan_interval, timedelta(minutes=55))

    coordinator = EPBUpdateCoordinator(
        hass,
        client,
        update_interval=scan_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return bool(unload_ok)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete stored tokens when the integration is removed."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)
