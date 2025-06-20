"""Constants for the BibKat integration."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "bibkat"

# Configuration
CONF_READER_NUMBER = "reader_number"
CONF_LIBRARY_URL: Final = "library_url"
CONF_ACCOUNTS: Final = "accounts"
CONF_ALIAS: Final = "alias"

# Account management
CONF_ACCOUNT_ID: Final = "account_id"
CONF_ADD_ANOTHER: Final = "add_another_account"

# API endpoints (defaults)
BASE_URL = "https://www.bibkat.de/boehl/"
LOGIN_URL = BASE_URL + "reader/"
FAMILY_URL = BASE_URL + "reader/family/"

# Update interval - 4x daily (every 6 hours)
UPDATE_INTERVAL = timedelta(hours=6)

# Detail fetch interval - 1x daily for renewal dates
DETAIL_FETCH_INTERVAL = timedelta(hours=24)

# Attributes
ATTR_BORROWED_MEDIA = "borrowed_media"
ATTR_TITLE = "title"
ATTR_AUTHOR = "author"
ATTR_DUE_DATE = "due_date"
ATTR_RENEWABLE = "renewable"
ATTR_DAYS_REMAINING = "days_remaining"
ATTR_MEDIA_ID = "media_id"
ATTR_ACCOUNT = "account"
ATTR_ACCOUNT_ALIAS: Final = "account_alias"
ATTR_LIBRARY: Final = "library"

# Balance attributes
ATTR_BALANCE: Final = "balance"
ATTR_BALANCE_CURRENCY: Final = "balance_currency"
ATTR_CARD_EXPIRY: Final = "card_expiry"
ATTR_RESERVATIONS: Final = "reservations"

# Services
SERVICE_RENEW_ALL = "renew_all"
SERVICE_RENEW_MEDIA = "renew_media"
SERVICE_TEST_NOTIFICATION = "test_notification"

# Options
OPT_NOTIFICATION_SERVICE: Final = "notification_service"
OPT_DUE_SOON_DAYS: Final = "due_soon_days"
OPT_NOTIFY_DUE_SOON: Final = "notify_due_soon"
OPT_NOTIFY_OVERDUE: Final = "notify_overdue"
OPT_NOTIFY_RENEWAL: Final = "notify_renewal"
OPT_NOTIFY_HIGH_BALANCE: Final = "notify_high_balance"
OPT_BALANCE_THRESHOLD: Final = "balance_threshold"
OPT_CREATE_ACCOUNT_CALENDARS: Final = "create_account_calendars"
OPT_USE_BROWSER: Final = "use_browser"  # Enable browser-based renewal date extraction

# Defaults
DEFAULT_DUE_SOON_DAYS: Final = 4
DEFAULT_BALANCE_THRESHOLD: Final = 10.0
DEFAULT_CREATE_ACCOUNT_CALENDARS: Final = False
DEFAULT_USE_BROWSER: Final = False