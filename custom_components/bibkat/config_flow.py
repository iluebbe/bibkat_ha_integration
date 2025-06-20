"""Config flow for BibKat integration with multi-account support."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .account_manager import Account, AccountManager
from .const import (
    CONF_ACCOUNTS,
    CONF_ADD_ANOTHER,
    CONF_ALIAS,
    CONF_LIBRARY_URL,
    DEFAULT_BALANCE_THRESHOLD,
    DEFAULT_DUE_SOON_DAYS,
    DEFAULT_USE_BROWSER,
    DOMAIN,
    OPT_BALANCE_THRESHOLD,
    OPT_DUE_SOON_DAYS,
    OPT_NOTIFICATION_SERVICE,
    OPT_NOTIFY_HIGH_BALANCE,
    OPT_NOTIFY_OVERDUE,
    OPT_NOTIFY_RENEWAL,
    OPT_USE_BROWSER,
)

_LOGGER = logging.getLogger(__name__)


def validate_url(url: str) -> str:
    """Validate and normalize the library URL."""
    # Ensure URL has proper format
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Ensure trailing slash
    if not url.endswith('/'):
        url += '/'
    
    # Validate it's a bibkat.de URL
    parsed = urlparse(url)
    if 'bibkat.de' not in parsed.netloc:
        raise InvalidURL
    
    return url


def extract_library_name(url: str) -> str:
    """Extract library name from URL."""
    # Extract from URL like https://www.bibkat.de/boehl/
    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')
    if path_parts and path_parts[0]:
        return path_parts[0].title()  # Capitalize first letter
    return "BibKat"


async def validate_credentials(
    hass: HomeAssistant, 
    library_url: str,
    username: str,
    password: str
) -> bool:
    """Validate credentials by attempting login."""
    from .auth_helper import BibKatAuthHelper
    from homeassistant.exceptions import ConfigEntryAuthFailed
    
    _LOGGER.info(f"Validating credentials for user {username} at {library_url}")
    
    auth_helper = BibKatAuthHelper(hass, library_url)
    
    try:
        # Try to create authenticated session
        session = await auth_helper.async_get_authenticated_session(
            username,
            password
        )
        # Close the session after validation
        await session.close()
        _LOGGER.info("Credentials validated successfully")
        return True
    except ConfigEntryAuthFailed as e:
        _LOGGER.error(f"Authentication failed: {e}")
        return False
    except Exception as e:
        _LOGGER.error(f"Unexpected error validating credentials: {e}", exc_info=True)
        return False


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BibKat with multi-account support."""

    VERSION = 2  # Bumped for multi-account support
    
    def __init__(self):
        """Initialize the config flow."""
        self._library_url: Optional[str] = None
        self._library_name: Optional[str] = None
        self._accounts: list[Dict[str, Any]] = []
        self._account_manager: Optional[AccountManager] = None
        self._is_migration = False
        
    async def async_step_user(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - library URL selection."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            try:
                # Validate and normalize URL
                self._library_url = validate_url(user_input[CONF_URL])
                self._library_name = extract_library_name(self._library_url)
                
                # Check if we already have an entry for this library
                existing_entry = None
                for entry in self._async_current_entries():
                    if entry.data.get(CONF_LIBRARY_URL) == self._library_url:
                        existing_entry = entry
                        break
                
                if existing_entry:
                    # Library already configured, go to options flow
                    return self.async_abort(reason="already_configured")
                
                # Continue to first account
                return await self.async_step_account()
                
            except InvalidURL:
                errors["base"] = "invalid_url"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default="https://www.bibkat.de/boehl/"): str,
            }),
            errors=errors,
            description_placeholders={
                "example_urls": "z.B. https://www.bibkat.de/boehl/ oder https://www.bibkat.de/kreuth/",
                "bibkat_info": self._get_bibkat_info_text()
            }
        )
    
    async def async_step_account(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle account configuration step."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            try:
                # Validate credentials
                if not await validate_credentials(
                    self.hass,
                    self._library_url,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD]
                ):
                    raise InvalidAuth
                
                # Add account to list
                account_data = {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_ALIAS: user_input.get(CONF_ALIAS) or f"Leser {user_input[CONF_USERNAME]}",
                }
                self._accounts.append(account_data)
                
                # Check if user wants to add another account
                if user_input.get(CONF_ADD_ANOTHER, False):
                    return await self.async_step_account()
                
                # Continue to features configuration
                return await self.async_step_features()
                
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        
        # Show account form
        account_number = len(self._accounts) + 1
        schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_ALIAS): str,
        })
        
        if account_number > 1:
            # Show "add another" checkbox only after first account
            schema = schema.extend({
                vol.Optional(CONF_ADD_ANOTHER, default=False): bool,
            })
        
        return self.async_show_form(
            step_id="account",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "library_name": self._library_name,
                "account_number": str(account_number),
            }
        )
    
    async def async_step_features(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure additional features like template sensors and dashboard."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            # Process feature selections
            if user_input.get("template_sensors", True):
                try:
                    from .helpers import create_template_sensors, get_template_format_type
                    format_type = get_template_format_type(self.hass)
                    await create_template_sensors(self.hass, force=True, format_type=format_type)
                    _LOGGER.info("Template sensors created successfully with format: %s", format_type)
                except Exception as e:
                    _LOGGER.error(f"Failed to create template sensors: {e}")
                    errors["template_sensors"] = "template_creation_failed"
            
            if user_input.get("dashboard", False):
                try:
                    from .discovery_dashboard import BibKatDiscoveryDashboard
                    generator = BibKatDiscoveryDashboard(self.hass)
                    
                    # Discover configuration
                    discovery_info = await generator.async_discover()
                    
                    # Generate dashboard
                    dashboard_data = generator.generate_dashboard(discovery_info)
                    
                    # Export to file
                    dashboard_path = await generator.export_dashboard("bibkat_dashboard.yaml")
                    _LOGGER.info(f"Dashboard created at: {dashboard_path}")
                    
                    # Show persistent notification
                    await self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "BibKat Dashboard erstellt",
                            "message": (
                                f"Dashboard wurde nach **bibkat_dashboard.yaml** exportiert.\n\n"
                                "**Nächste Schritte:**\n"
                                "1. Gehe zu Einstellungen → Dashboards\n"
                                "2. Klicke auf 'Dashboard hinzufügen'\n"
                                "3. Wähle 'Aus YAML-Datei laden'\n"
                                "4. Gib ein: `bibkat_dashboard.yaml`\n\n"
                                "Das Dashboard enthält alle Bücher sortiert nach Fälligkeit."
                            ),
                            "notification_id": "bibkat_dashboard_created",
                        }
                    )
                except Exception as e:
                    _LOGGER.error(f"Failed to create dashboard: {e}")
                    errors["dashboard"] = "dashboard_creation_failed"
            
            # If no errors, create the entry
            if not errors:
                return await self._create_entry()
        
        return self.async_show_form(
            step_id="features",
            data_schema=vol.Schema({
                vol.Optional("template_sensors", default=True): bool,
                vol.Optional("dashboard", default=False): bool,
            }),
            errors=errors,
            description_placeholders={
                "template_info": "Template-Sensoren ermöglichen erweiterte Dashboards und stabile UI-Referenzen für dynamische Medien-Entitäten.",
                "dashboard_info": "Erstellt ein vorkonfiguriertes Dashboard mit allen Büchern, sortiert nach Fälligkeit.",
                "template_note": "Nach der Erstellung fügen Sie einfach '!include bibkat_template_slots.yaml' zu Ihrer template: Konfiguration hinzu.",
                "dashboard_note": "Das Dashboard wird als 'bibkat_dashboard.yaml' direkt in Ihrem /config Ordner erstellt."
            }
        )
    
    async def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        # Create unique ID for the library
        unique_id = f"library_{self._library_url}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        
        # Create title
        account_count = len(self._accounts)
        if account_count == 1:
            title = f"{self._library_name} - {self._accounts[0][CONF_ALIAS]}"
        else:
            title = f"{self._library_name} - {account_count} Konten"
        
        # Create entry data
        data = {
            CONF_LIBRARY_URL: self._library_url,
            CONF_ACCOUNTS: self._accounts,
        }
        
        return self.async_create_entry(title=title, data=data)
    
    async def async_step_import(self, import_data: Dict[str, Any]) -> FlowResult:
        """Handle import from YAML (migration from single account)."""
        self._is_migration = True
        
        # Extract data for migration
        self._library_url = import_data.get(CONF_URL, "https://www.bibkat.de/boehl/")
        self._library_name = extract_library_name(self._library_url)
        
        # Create account from old format
        account_data = {
            CONF_USERNAME: import_data.get(CONF_USERNAME),
            CONF_PASSWORD: import_data.get(CONF_PASSWORD),
            CONF_ALIAS: f"Leser {import_data.get(CONF_USERNAME)}",
        }
        self._accounts = [account_data]
        
        # Create entry
        return await self._create_entry()
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options for BibKat."""
    
    def __init__(self) -> None:
        """Initialize options flow."""
        self._account_manager: Optional[AccountManager] = None
        self._selected_account: Optional[str] = None
    
    async def async_step_init(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        # Show menu with both notifications and accounts options
        return await self.async_step_menu()
    
    async def async_step_menu(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Show options menu."""
        # Show notifications, accounts, and features management
        menu_options = ["notifications", "accounts", "features"]
        return self.async_show_menu(
            step_id="menu",
            menu_options=menu_options,
        )
    
    async def async_step_accounts(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage accounts - show discovered family members."""
        if user_input is not None:
            # User selected a family member to add credentials for
            selected_account = user_input.get("selected_account")
            if selected_account and selected_account != "none":
                self._selected_account = selected_account
                return await self.async_step_add_credentials()
            return self.async_create_entry(title="", data={})
        
        # Get coordinator to find discovered accounts
        entry_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        coordinator = entry_data.get("coordinator")
        
        if not coordinator or not coordinator.data:
            return self.async_show_form(
                step_id="accounts",
                data_schema=vol.Schema({}),
                errors={"base": "no_data"},
                description_placeholders={
                    "info": "Keine Daten verfügbar. Bitte warten Sie, bis die Integration Daten geladen hat."
                },
            )
        
        # Find unconfigured accounts
        unconfigured_accounts = []
        for account_id, account_data in coordinator.data.get("accounts", {}).items():
            if not account_data.get("is_configured", True):
                # This is an unconfigured family member
                alias = account_data.get("account_alias", f"Leser {account_id}")
                media_count = account_data.get("total_borrowed", 0)
                reservation_count = account_data.get("total_reservations", 0)
                
                label = f"{alias} ({account_id}) - {media_count} Medien, {reservation_count} Vormerkungen"
                unconfigured_accounts.append((account_id, label))
        
        if not unconfigured_accounts:
            return self.async_show_form(
                step_id="accounts",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "info": "Keine unconfigurierten Familienkonten gefunden. Alle Familienmitglieder sind bereits konfiguriert."
                },
            )
        
        # Add "none" option
        account_options = [("none", "Kein Konto hinzufügen")] + unconfigured_accounts
        
        schema = vol.Schema({
            vol.Required("selected_account", default="none"): vol.In(
                dict(account_options)
            ),
        })
        
        return self.async_show_form(
            step_id="accounts",
            data_schema=schema,
            description_placeholders={
                "info": "Wählen Sie ein Familienkonto aus, um Anmeldedaten hinzuzufügen:"
            },
        )
    
    async def async_step_add_credentials(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Add credentials for a selected family member."""
        errors = {}
        
        if user_input is not None:
            try:
                _LOGGER.info(f"Adding credentials for account {self._selected_account}")
                
                # Validate credentials
                username = self._selected_account  # Account number is the username
                password = user_input[CONF_PASSWORD]
                alias = user_input.get(CONF_ALIAS, f"Leser {username}")
                
                _LOGGER.debug(f"Username: {username}, Alias: {alias}")
                
                # Get library URL from config
                library_url = self.config_entry.data.get(CONF_LIBRARY_URL)
                _LOGGER.debug(f"Library URL: {library_url}")
                
                # Test authentication
                session = async_get_clientsession(self.hass)
                api = BibKatAPI(session, library_url)
                
                _LOGGER.info(f"Testing login for account {username}")
                if await api.login(username, password):
                    _LOGGER.info(f"Login successful for account {username}")
                    
                    # Success - add account to configuration
                    entry_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
                    account_manager = entry_data.get("account_manager")
                    
                    if account_manager:
                        # Get library
                        library = account_manager.get_library(library_url)
                        if library:
                            # Create and add account
                            _LOGGER.info(f"Adding account to library")
                            from .account_manager import Account
                            account = Account(
                                username=username,
                                password=password,
                                alias=alias,
                                library_url=library_url,
                            )
                            library.add_account(account)
                            
                            # Save account manager
                            _LOGGER.info(f"Saving account manager")
                            await account_manager.async_save()
                            
                            # Update config entry data
                            accounts_data = self.config_entry.data.get(CONF_ACCOUNTS, [])
                            accounts_data.append({
                                CONF_USERNAME: username,
                                CONF_PASSWORD: password,
                                CONF_ALIAS: alias,
                            })
                            
                            new_data = dict(self.config_entry.data)
                            new_data[CONF_ACCOUNTS] = accounts_data
                            
                            _LOGGER.info(f"Updating config entry")
                            self.hass.config_entries.async_update_entry(
                                self.config_entry,
                                data=new_data,
                            )
                            
                            # Request coordinator refresh
                            coordinator = entry_data.get("coordinator")
                            if coordinator:
                                _LOGGER.info(f"Requesting coordinator refresh")
                                await coordinator.async_request_refresh()
                            
                            return self.async_create_entry(
                                title="", 
                                data={},
                                description_placeholders={
                                    "success": f"Konto {username} ({alias}) erfolgreich hinzugefügt!"
                                }
                            )
                        else:
                            _LOGGER.error(f"Library not found for URL {library_url}")
                            errors["base"] = "unknown"
                    else:
                        _LOGGER.error("Account manager not found")
                        errors["base"] = "unknown"
                else:
                    _LOGGER.warning(f"Login failed for account {username}")
                    errors["base"] = "invalid_auth"
                    
            except Exception as e:
                _LOGGER.exception(f"Error in async_step_add_credentials: {e}")
                errors["base"] = "unknown"
        
        # Show form
        schema = vol.Schema({
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_ALIAS, default=f"Leser {self._selected_account}"): str,
        })
        
        return self.async_show_form(
            step_id="add_credentials",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "account": self._selected_account,
                "info": f"Geben Sie das Passwort für Konto {self._selected_account} ein:"
            },
        )
    
    async def async_step_notifications(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure notifications."""
        if user_input is not None:
            # Update options
            return self.async_create_entry(title="", data=user_input)
        
        # Get current options
        options = self.config_entry.options
        
        # Build schema
        schema = vol.Schema({
            vol.Optional(
                OPT_NOTIFICATION_SERVICE,
                default=options.get(OPT_NOTIFICATION_SERVICE, "")
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._get_notification_services(),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                OPT_DUE_SOON_DAYS,
                default=options.get(OPT_DUE_SOON_DAYS, DEFAULT_DUE_SOON_DAYS)
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=14)),
            vol.Optional(
                OPT_NOTIFY_OVERDUE,
                default=options.get(OPT_NOTIFY_OVERDUE, True)
            ): bool,
            vol.Optional(
                OPT_NOTIFY_RENEWAL,
                default=options.get(OPT_NOTIFY_RENEWAL, True)
            ): bool,
            vol.Optional(
                OPT_NOTIFY_HIGH_BALANCE,
                default=options.get(OPT_NOTIFY_HIGH_BALANCE, True)
            ): bool,
            vol.Optional(
                OPT_BALANCE_THRESHOLD,
                default=options.get(OPT_BALANCE_THRESHOLD, DEFAULT_BALANCE_THRESHOLD)
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=100.0)),
            vol.Optional(
                OPT_USE_BROWSER,
                default=options.get(OPT_USE_BROWSER, DEFAULT_USE_BROWSER)
            ): bool,
        })
        
        return self.async_show_form(
            step_id="notifications",
            data_schema=schema,
        )
    
    def _get_bibkat_info_text(self) -> str:
        """Get localized BibKat info text based on user language."""
        user_language = self.hass.config.language
        
        if user_language == "de":
            return "Besuchen Sie https://www.bibkat.de/ um Ihre Bibliothek zu finden. Die URL endet normalerweise mit /ihrestadt/"
        else:
            return "Visit https://www.bibkat.de/ to find your library. The URL usually ends with /yourcity/"
    
    def _get_notification_services(self) -> list[str]:
        """Get available notification services."""
        services = [""]  # Empty option for no notifications
        
        # Get all notify services
        if hasattr(self.hass.services, "async_services"):
            notify_services = self.hass.services.async_services().get("notify", {})
            for service_name in notify_services:
                if service_name != "notify":  # Skip the base notify service
                    services.append(f"notify.{service_name}")
        
        return services
    
    async def async_step_features(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure additional features for existing integration."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            # Process feature selections
            if user_input.get("template_sensors", False):
                try:
                    from .helpers import create_template_sensors, get_template_format_type
                    format_type = get_template_format_type(self.hass)
                    await create_template_sensors(self.hass, force=True, format_type=format_type)
                    _LOGGER.info("Template sensors created successfully with format: %s", format_type)
                except Exception as e:
                    _LOGGER.error(f"Failed to create template sensors: {e}")
                    errors["template_sensors"] = "template_creation_failed"
            
            if user_input.get("dashboard", False):
                try:
                    from .discovery_dashboard import BibKatDiscoveryDashboard
                    generator = BibKatDiscoveryDashboard(self.hass)
                    
                    # Discover configuration
                    discovery_info = await generator.async_discover()
                    
                    # Generate dashboard
                    dashboard_data = generator.generate_dashboard(discovery_info)
                    
                    # Export to file
                    dashboard_path = await generator.export_dashboard("bibkat_dashboard.yaml")
                    _LOGGER.info(f"Dashboard created at: {dashboard_path}")
                    
                    # Show persistent notification
                    await self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "BibKat Dashboard erstellt",
                            "message": (
                                f"Dashboard wurde nach **bibkat_dashboard.yaml** exportiert.\n\n"
                                "**Nächste Schritte:**\n"
                                "1. Gehe zu Einstellungen → Dashboards\n"
                                "2. Klicke auf 'Dashboard hinzufügen'\n"
                                "3. Wähle 'Aus YAML-Datei laden'\n"
                                "4. Gib ein: `bibkat_dashboard.yaml`\n\n"
                                "Das Dashboard enthält alle Bücher sortiert nach Fälligkeit."
                            ),
                            "notification_id": "bibkat_dashboard_created",
                        }
                    )
                except Exception as e:
                    _LOGGER.error(f"Failed to create dashboard: {e}")
                    errors["dashboard"] = "dashboard_creation_failed"
            
            # If no errors, save options
            if not errors:
                return self.async_create_entry(title="", data={})
        
        # Check current status
        import os
        config_dir = self.hass.config.path()
        template_file = os.path.join(config_dir, "bibkat_template_slots.yaml")
        file_exists = os.path.exists(template_file)
        sensors_exist = self.hass.states.get("sensor.bibliothek_slot_1") is not None
        
        if sensors_exist:
            template_status = "✅ Sensoren aktiv"
        elif file_exists:
            template_status = "⚠️ Datei erstellt, aber nicht in configuration.yaml eingebunden"
        else:
            template_status = "❌ Nicht erstellt"
        
        return self.async_show_form(
            step_id="features",
            data_schema=vol.Schema({
                vol.Optional("template_sensors", default=False): bool,
                vol.Optional("dashboard", default=False): bool,
            }),
            errors=errors,
            description_placeholders={
                "template_status": f"Template-Sensoren: {template_status}",
                "template_info": "Template-Sensoren ermöglichen erweiterte Dashboards und stabile UI-Referenzen für dynamische Medien-Entitäten.",
                "dashboard_info": "Erstellt ein vorkonfiguriertes Dashboard mit allen Büchern, sortiert nach Fälligkeit.",
                "template_note": "Nach der Erstellung fügen Sie '!include bibkat_template_slots.yaml' zu Ihrer template: Konfiguration hinzu.",
                "dashboard_note": "Das Dashboard wird als 'bibkat_dashboard.yaml' in Ihrem /config Ordner erstellt."
            }
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidURL(HomeAssistantError):
    """Error to indicate the URL is invalid."""