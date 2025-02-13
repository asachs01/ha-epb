"""Constants for the EPB integration."""
from datetime import timedelta

DOMAIN = "epb"
SCAN_INTERVAL = timedelta(minutes=15)

# Configuration
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# API endpoints
BASE_URL = "https://api.epb.com/web/api/v1"
LOGIN_URL = f"{BASE_URL}/login/"
ACCOUNT_LINKS_URL = f"{BASE_URL}/account-links/"
USAGE_URL = f"{BASE_URL}/usage/power/permanent/compare/daily" 