"""The BibKat integration with multi-account support."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.template import Template

from .account_manager import Account, AccountManager
from .const import (
    CONF_ACCOUNTS,
    CONF_ALIAS,
    CONF_LIBRARY_URL,
    DOMAIN,
    SERVICE_RENEW_ALL,
    SERVICE_RENEW_MEDIA,
    SERVICE_TEST_NOTIFICATION,
)
from .coordinator import BibKatMultiAccountCoordinator
from .notification_manager import NotificationManager
from .notification_actions import NotificationActionHandler

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BibKat from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Get or create account manager
    if "account_manager" not in hass.data[DOMAIN]:
        account_manager = AccountManager(hass)
        await account_manager.async_load()
        hass.data[DOMAIN]["account_manager"] = account_manager
    else:
        account_manager = hass.data[DOMAIN]["account_manager"]
    
    # Get or create notification manager
    if "notification_manager" not in hass.data[DOMAIN]:
        notification_manager = NotificationManager(hass, account_manager)
        await notification_manager.async_setup()
        hass.data[DOMAIN]["notification_manager"] = notification_manager
    else:
        notification_manager = hass.data[DOMAIN]["notification_manager"]
    
    # Get or create notification action handler
    if "notification_action_handler" not in hass.data[DOMAIN]:
        action_handler = NotificationActionHandler(hass)
        await action_handler.async_setup()
        hass.data[DOMAIN]["notification_action_handler"] = action_handler
    else:
        action_handler = hass.data[DOMAIN]["notification_action_handler"]
    
    # Handle migration from v1 config
    if entry.version == 1:
        # Migrate from single account to multi-account
        library_url = entry.data.get(CONF_URL, "https://www.bibkat.de/boehl/")
        username = entry.data.get(CONF_USERNAME)
        password = entry.data.get(CONF_PASSWORD)
        
        if username and password:
            # Create library and account
            library = await account_manager.migrate_from_config_entry(entry.data)
            
            # Update config entry
            new_data = {
                CONF_LIBRARY_URL: library_url,
                CONF_ACCOUNTS: [{
                    CONF_USERNAME: username,
                    CONF_PASSWORD: password,
                    CONF_ALIAS: f"Leser {username}",
                }],
            }
            
            hass.config_entries.async_update_entry(
                entry,
                data=new_data,
                version=2,
            )
    
    # Get library URL and accounts
    library_url = entry.data.get(CONF_LIBRARY_URL)
    accounts_data = entry.data.get(CONF_ACCOUNTS, [])
    
    if not library_url or not accounts_data:
        raise ConfigEntryNotReady("No library URL or accounts configured")
    
    # Add or update library in account manager
    library_name = library_url.rstrip('/').split('/')[-1].title()
    library = account_manager.get_library(library_url)
    if not library:
        library = account_manager.add_library(library_url, library_name)
    
    # Add accounts to library
    for account_data in accounts_data:
        account = Account(
            username=account_data[CONF_USERNAME],
            password=account_data[CONF_PASSWORD],
            alias=account_data.get(CONF_ALIAS, ""),
            library_url=library_url,
        )
        library.add_account(account)
    
    # Save account manager
    await account_manager.async_save()
    
    # Test authentication for all accounts
    session = async_get_clientsession(hass)
    for account in library.accounts:
        if not await account_manager.test_account(account, session):
            _LOGGER.warning(
                "Unable to authenticate account %s for library %s",
                account.username,
                library_name
            )
    
    # Create renewal rules manager
    from .renewal_rules import RenewalRulesManager
    renewal_rules_manager = RenewalRulesManager(hass)
    
    # Create coordinator
    coordinator = BibKatMultiAccountCoordinator(
        hass,
        entry,
        account_manager,
        library_url,
        renewal_rules_manager
    )
    await coordinator.async_config_entry_first_refresh()
    
    # Store data
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "account_manager": account_manager,
        "renewal_rules_manager": renewal_rules_manager,
    }
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    async def handle_renew_all(call: Any) -> None:
        """Handle the renew all service call."""
        # Get account ID from service call data (optional)
        account_id = call.data.get("account_id")
        
        # Find the coordinator for this library
        for entry_data in hass.data[DOMAIN].values():
            if isinstance(entry_data, dict) and "coordinator" in entry_data:
                coordinator = entry_data["coordinator"]
                if coordinator.library_url == library_url:
                    result = await coordinator.async_renew_all_media(account_id)
                    _LOGGER.info("Renew all media result: %s", result)
                    
                    # Send notification using notification manager
                    await notification_manager.send_renewal_notification(
                        library_url,
                        result
                    )
                    
                    # Also create persistent notification (legacy)
                    if result.get('errors'):
                        message = f"{result['message']}\n\n"
                        message += "Fehler:\n" + "\n".join(result['errors'])
                        await hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "message": message,
                                "title": "Bibliothek Verlängerung",
                                "notification_id": "bibkat_renewal"
                            }
                        )
                    elif result.get('message'):
                        await hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "message": result['message'],
                                "title": "Bibliothek Verlängerung",
                                "notification_id": "bibkat_renewal"
                            }
                        )
                    break
    
    # Test notification service handler
    async def handle_test_notification(call: Any) -> None:
        """Handle the test notification service call."""
        # Get library URL from service call or use first available
        library_url_param = call.data.get("library_url")
        
        if library_url_param:
            success = await notification_manager.test_notification(library_url_param)
        else:
            # Use library URL from current entry
            success = await notification_manager.test_notification(library_url)
        
        if not success:
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": "Keine Benachrichtigungsdienst konfiguriert für diese Bibliothek",
                    "title": "BibKat Test-Benachrichtigung",
                    "notification_id": "bibkat_test_notification"
                }
            )
    
    # Service handler for renewing individual media
    async def handle_renew_media(call: Any) -> None:
        """Handle the renew media service call."""
        media_id = call.data.get("media_id")
        account_id = call.data.get("account_id")
        
        # If no media_id provided, try to get it from the target entity
        if not media_id and hasattr(call, 'target'):
            # Get entity IDs from the service call
            entity_ids = []
            if hasattr(call.target, 'entity_id'):
                entity_ids = call.target.entity_id
            
            if entity_ids:
                # Use the first entity (should only be one for renew_media)
                entity_id = entity_ids[0] if isinstance(entity_ids, list) else entity_ids
                
                # Find the button entity and get its media_id
                entity = hass.states.get(entity_id)
                if entity and entity.attributes.get("media_id"):
                    media_id = entity.attributes["media_id"]
                    _LOGGER.info(f"Got media_id {media_id} from entity {entity_id}")
                else:
                    _LOGGER.error(f"Entity {entity_id} has no media_id attribute")
                    return
        
        if not media_id:
            _LOGGER.error("No media_id provided for renew_media service")
            return
        
        # Find the coordinator and renew the specific media
        for entry_data in hass.data[DOMAIN].values():
            if isinstance(entry_data, dict) and "coordinator" in entry_data:
                coordinator = entry_data["coordinator"]
                if coordinator.library_url == library_url:
                    result = await coordinator.async_renew_media(media_id, account_id)
                    _LOGGER.info("Renew media %s result: %s", media_id, result)
                    
                    # Send notification
                    if result.get('success'):
                        message = f"Medium '{result.get('title', media_id)}' wurde verlängert bis {result.get('new_due_date', 'unbekannt')}"
                    else:
                        message = f"Medium '{result.get('title', media_id)}' konnte nicht verlängert werden: {result.get('message', 'Unbekannter Fehler')}"
                    
                    hass.components.persistent_notification.async_create(
                        message,
                        "Bibliothek Verlängerung",
                        "bibkat_renewal_media"
                    )
                    break
    
    # Register services only once
    if not hass.services.has_service(DOMAIN, SERVICE_RENEW_ALL):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RENEW_ALL,
            handle_renew_all,
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_RENEW_MEDIA):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RENEW_MEDIA,
            handle_renew_media,
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_TEST_NOTIFICATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_TEST_NOTIFICATION,
            handle_test_notification,
        )
    
    # Auto-register template sensors if not already done
    await _ensure_template_sensors(hass)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        
        # Check if this was the last entry
        if not any(
            isinstance(data, dict) and "coordinator" in data
            for data in hass.data[DOMAIN].values()
        ):
            # Remove services
            hass.services.async_remove(DOMAIN, SERVICE_RENEW_ALL)
            hass.services.async_remove(DOMAIN, SERVICE_TEST_NOTIFICATION)
            
            # Stop notification action handler
            if "notification_action_handler" in hass.data[DOMAIN]:
                await hass.data[DOMAIN]["notification_action_handler"].async_stop()
                hass.data[DOMAIN].pop("notification_action_handler")
            
            # Stop notification manager
            if "notification_manager" in hass.data[DOMAIN]:
                await hass.data[DOMAIN]["notification_manager"].async_stop()
                hass.data[DOMAIN].pop("notification_manager")
            
            # Remove account manager if no more entries
            if "account_manager" in hass.data[DOMAIN]:
                hass.data[DOMAIN].pop("account_manager")
    
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating config entry from version %s", config_entry.version)
    
    if config_entry.version == 1:
        # Migration handled in async_setup_entry
        return True
    
    return True


async def _ensure_template_sensors(hass: HomeAssistant) -> None:
    """Ensure template sensors are registered."""
    # Check if template sensors already exist
    if hass.states.get("sensor.bibliothek_slot_1") is not None:
        _LOGGER.debug("Template sensors already registered")
        return
    
    _LOGGER.info("Auto-registering BibKat template sensors")
    
    # Import the template generator
    from .template_sensors import create_template_sensors
    
    # Create and register all template sensors
    await create_template_sensors(hass)