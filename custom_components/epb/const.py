"""Constants for the EPB integration."""

from datetime import timedelta

DOMAIN = "epb"

# Remove the SCAN_INTERVAL constant as we'll use Home Assistant's native mechanisms
DEFAULT_SCAN_INTERVAL = timedelta(
    minutes=15
)  # We'll use this as a default but allow configuration

# Configuration
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_TOKENS = "tokens"

# API endpoints
BASE_URL = "https://api.epb.com/web/api/v1"
LOGIN_URL = f"{BASE_URL}/login/"
ACCOUNT_LINKS_URL = f"{BASE_URL}/account-links/"
USAGE_URL = f"{BASE_URL}/usage/power/permanent/compare/daily"
