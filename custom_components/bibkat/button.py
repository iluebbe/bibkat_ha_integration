"""Button platform for BibKat - Individual media button entities."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .account_manager import AccountManager, Library

# Import coordinator for runtime use
from .coordinator import BibKatMultiAccountCoordinator

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    from .account_manager import AccountManager
    from .coordinator import BibKatMultiAccountCoordinator
    
    _LOGGER.info("Setting up button platform for entry: %s", config_entry.entry_id)
    
    coordinator: BibKatMultiAccountCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    account_manager: AccountManager = hass.data[DOMAIN][config_entry.entry_id]["account_manager"]
    library_url: str = config_entry.data["library_url"]
    
    _LOGGER.debug("Library URL: %s", library_url)
    
    # Get library
    library: Optional[Library] = account_manager.get_library(library_url)
    if not library:
        _LOGGER.error("Library not found for URL: %s", library_url)
        return
    
    _LOGGER.info("Found library: %s", library.name)
    
    # Create entity manager
    entity_manager: MediaEntityManager = MediaEntityManager(
        coordinator=coordinator,
        library_name=library.name,
        async_add_entities=async_add_entities,
    )
    
    # Store entity manager for coordinator updates
    hass.data[DOMAIN][config_entry.entry_id]["media_entity_manager"] = entity_manager
    
    # Register update listener
    @callback
    def handle_coordinator_update() -> None:
        """Handle coordinator data update."""
        _LOGGER.info("Button platform: Coordinator update triggered")
        
        if not coordinator.data:
            _LOGGER.warning("No coordinator data available")
            return
            
        all_media: List[Dict[str, Any]] = coordinator.data.get("all_media", [])
        _LOGGER.info(f"Button platform update: Found {len(all_media)} media items")
        
        # Log details of each media item
        for idx, media in enumerate(all_media):
            _LOGGER.debug(
                f"Media {idx + 1}: ID={media.get('media_id', 'NO_ID')}, "
                f"Title='{media.get('title', 'NO_TITLE')}', "
                f"Account={media.get('account_id', 'NO_ACCOUNT')}, "
                f"External={media.get('external_account', False)}"
            )
        
        entity_manager.update_entities(all_media)
    
    # Initial update
    _LOGGER.info("Performing initial button entity update")
    handle_coordinator_update()
    
    # Listen for updates
    _LOGGER.info("Registering coordinator listener for button updates")
    coordinator.async_add_listener(handle_coordinator_update)
    
    # Log setup completion
    _LOGGER.info(
        f"Button platform setup complete. Entity manager has {len(entity_manager._known_media_ids)} media IDs tracked"
    )


class MediaEntityManager:
    """Manages dynamic creation/removal of media button entities."""
    
    def __init__(
        self,
        coordinator: BibKatMultiAccountCoordinator,
        library_name: str,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Initialize the entity manager."""
        from .coordinator import BibKatMultiAccountCoordinator
        
        self._coordinator: BibKatMultiAccountCoordinator = coordinator
        self._library_name: str = library_name
        self._async_add_entities: AddEntitiesCallback = async_add_entities
        self._entities: Dict[str, BibKatMediaButton] = {}
        self._known_media_ids: Set[str] = set()
    
    @callback
    def update_entities(self, media_list: List[Dict[str, Any]]) -> None:
        """Update entities based on current media list."""
        _LOGGER.debug(f"MediaEntityManager.update_entities called with {len(media_list)} media items")
        
        current_media_ids: Set[str] = set()
        for media in media_list:
            media_id = media.get("media_id")
            if media_id:
                current_media_ids.add(media_id)
            else:
                _LOGGER.warning(f"Media item without media_id: {media}")
        
        # Create new entities
        new_entities: List[BibKatMediaButton] = []
        for media in media_list:
            media_id: str = media.get("media_id", "")
            if not media_id:
                _LOGGER.warning(f"Skipping media without ID: {media}")
                continue
                
            if media_id not in self._known_media_ids:
                _LOGGER.info(f"Creating new button entity for media: {media.get('title', 'Unknown')} (ID: {media_id})")
                entity: BibKatMediaButton = BibKatMediaButton(
                    coordinator=self._coordinator,
                    media=media,
                    library_name=self._library_name,
                )
                self._entities[media_id] = entity
                new_entities.append(entity)
                self._known_media_ids.add(media_id)
        
        if new_entities:
            _LOGGER.info(f"Adding {len(new_entities)} new media button entities")
            # Log each entity being added
            for entity in new_entities:
                _LOGGER.info(
                    f"Adding button entity: {entity.entity_id} "
                    f"(unique_id: {entity.unique_id}, name: {entity.name})"
                )
            self._async_add_entities(new_entities)
            _LOGGER.info("Entities added successfully")
        else:
            _LOGGER.debug("No new entities to add")
        
        # Remove entities for returned media
        media_ids_to_remove: List[str] = []
        for media_id in self._known_media_ids:
            if media_id not in current_media_ids:
                media_ids_to_remove.append(media_id)
        
        for media_id in media_ids_to_remove:
            if media_id in self._entities:
                # Mark entity as unavailable first
                self._entities[media_id]._attr_available = False
                self._entities[media_id].async_write_ha_state()
                # Remove from tracking
                del self._entities[media_id]
                self._known_media_ids.remove(media_id)
                _LOGGER.info("Removed entity for returned media: %s", media_id)
        
        # Update existing entities
        for media in media_list:
            media_id: str = media["media_id"]
            if media_id in self._entities:
                self._entities[media_id].update_media(media)


class BibKatMediaButton(CoordinatorEntity[BibKatMultiAccountCoordinator], ButtonEntity):
    """Button entity for individual borrowed medium."""
    
    _attr_has_entity_name: bool = False
    
    def __init__(
        self,
        coordinator: BibKatMultiAccountCoordinator,
        media: Dict[str, Any],
        library_name: str,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator)
        
        self._media: Dict[str, Any] = media
        self._library_name: str = library_name
        
        # Create safe entity ID from title and media ID
        safe_title: str = self._create_safe_id(media.get("title", "unknown"))
        media_id_suffix: str = media["media_id"].split("-")[-1] if "-" in media["media_id"] else media["media_id"]
        
        # Set unique attributes
        self._attr_unique_id: str = f"bibkat_{library_name}_{media['media_id']}_button"
        self.entity_id: str = f"button.bibkat_{library_name}_{safe_title}_{media_id_suffix}"
        
        # Set device info
        account_id: str = media.get("account_id", "unknown")
        
        # For external accounts, create a special device
        if media.get("external_account", False):
            self._attr_device_info: DeviceInfo = DeviceInfo(
                identifiers={(DOMAIN, f"family_{library_name}")},
                name=f"{library_name} - Familienmitglieder",
                manufacturer="BibKat",
                model="Familienkonto",
            )
        else:
            self._attr_device_info: DeviceInfo = DeviceInfo(
                identifiers={(DOMAIN, account_id)},
                name=f"{library_name} - {media.get('account_alias', 'Unknown')}",
                manufacturer="BibKat",
                model="Bibliothekskonto",
            )
        
        self._update_attributes()
    
    def _create_safe_id(self, text: str) -> str:
        """Create a safe entity ID from text."""
        # Remove special characters and convert to lowercase
        safe: str = re.sub(r'[^a-zA-Z0-9äöüÄÖÜß]+', '_', text.lower())
        safe = safe.strip('_')
        # Limit length
        if len(safe) > 30:
            safe = safe[:30].rstrip('_')
        return safe
    
    @callback
    def update_media(self, media: Dict[str, Any]) -> None:
        """Update media data."""
        self._media = media
        self._update_attributes()
        self.async_write_ha_state()
    
    def _update_attributes(self) -> None:
        """Update entity attributes based on media data."""
        days: int = self._media.get("days_remaining", 0)
        renewable: bool = self._media.get("is_renewable_now", False)
        renewal_date_iso: Optional[str] = self._media.get("renewal_date_iso")
        
        # Set name with status
        title: str = self._media.get("title", "Unknown")
        
        # Add owner info for external accounts
        name_prefix = ""
        if self._media.get("external_account", False):
            owner = self._media.get("account_alias", "Unknown").replace("Leser ", "")
            name_prefix = f"[{owner}] "
        
        # Add renewal info to name if not renewable yet
        renewal_info = ""
        if not renewable and renewal_date_iso:
            try:
                from datetime import datetime, date
                renewal_date = date.fromisoformat(renewal_date_iso)
                days_until_renewable = (renewal_date - date.today()).days
                if days_until_renewable > 0:
                    renewal_info = f" (↻{days_until_renewable}d)"
            except:
                pass
        
        if days < 0:
            self._attr_name = f"⚠️ {name_prefix}{title} (überfällig!){renewal_info}"
            self._attr_icon = "mdi:book-alert"
        elif days <= 3:
            self._attr_name = f"⏰ {name_prefix}{title} ({days}d){renewal_info}"
            self._attr_icon = "mdi:book-clock"
        else:
            self._attr_name = f"📚 {name_prefix}{title} ({days}d){renewal_info}"
            self._attr_icon = "mdi:book-check"
        
        # Disable button if not renewable
        self._attr_available = renewable
        
        # Format renewal date for attributes
        renewal_date_formatted = ""
        days_until_renewable = None
        if renewal_date_iso:
            try:
                from datetime import datetime, date
                renewal_date = date.fromisoformat(renewal_date_iso)
                days_until_renewable = (renewal_date - date.today()).days
                # Format the date in German format
                renewal_date_formatted = renewal_date.strftime("%d.%m.%Y")
            except:
                renewal_date_formatted = self._media.get("renewal_date", "")
        
        # Set extra attributes
        self._attr_extra_state_attributes: Dict[str, Any] = {
            "title": self._media.get("title", ""),
            "author": self._media.get("author", ""),
            "account": self._media.get("account", ""),
            "account_alias": self._media.get("account_alias", ""),
            "due_date": self._media.get("due_date", ""),
            "due_date_iso": self._media.get("due_date_iso"),
            "days_remaining": days,
            "renewable": self._media.get("renewable", False),
            "is_renewable_now": renewable,
            "media_id": self._media.get("media_id", ""),
            "renewal_date": self._media.get("renewal_date", ""),
            "renewal_date_iso": self._media.get("renewal_date_iso"),
            "renewal_date_formatted": renewal_date_formatted,
            "days_until_renewable": days_until_renewable,
            "found_on": self._media.get("found_on", []),
            "is_configured": self._media.get("is_configured", True),  # Default True for backward compat
            "is_family_only": self._media.get("found_on", []) == ["family"],  # Only found on family page
        }
    
    async def _get_api_for_media(self):
        """Get the API instance for this media item."""
        try:
            # Get account manager
            from .account_manager import AccountManager
            account_manager: AccountManager = self.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["account_manager"]
            library = account_manager.get_library(self.coordinator.library_url)
            
            if not library:
                return None
            
            # Get the account that owns this media
            owner_number = self._media.get("owner_number", "main")
            account_id = self._media.get("account_id")
            
            # Try to get API for the owner account
            if account_id:
                account = library.get_account(account_id)
                if account and account.api:
                    return account.api
            
            # Fallback to any available API
            for account in library.accounts.values():
                if account.api:
                    return account.api
            
            return None
        except Exception as e:
            _LOGGER.error(f"Error getting API for media: {e}")
            return None
    
    async def async_press(self) -> None:
        """Handle the button press - renew this specific medium."""
        media_id = self._media.get('media_id')
        media_title = self._media.get('title', 'Unknown')
        _LOGGER.info(f"Button pressed for media: {media_title} (ID: {media_id})")

        # Rufen Sie immer die Erneuerungsmethode des Coordinators auf.
        # Diese kümmert sich um die gesamte komplexe Logik (Regeln, Browser, Fallback).
        result = await self.coordinator.async_renew_media(media_id)
        _LOGGER.info(f"Renewal result for {media_title}: {result}")

        if result.get("success"):
            # Die erfolgreiche Erneuerung wird durch den nächsten Coordinator-Refresh angezeigt.
            # Wir können eine temporäre Benachrichtigung anzeigen.
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "BibKat Verlängerung",
                    "message": f"'{media_title}' wurde erfolgreich verlängert.",
                    "notification_id": f"bibkat_renewal_success_{media_id}",
                }
            )
            # Der Coordinator-Refresh in async_renew_media kümmert sich um den Rest.
        else:
            # Die Erneuerung ist fehlgeschlagen.
            message = result.get("message", "Unbekannter Fehler")
            
            # Wenn ein Verlängerungsdatum extrahiert wurde, aktualisiere es lokal
            if result.get("renewal_date_iso"):
                self._media["renewal_date"] = result.get("renewal_date", "")
                self._media["renewal_date_iso"] = result.get("renewal_date_iso")
                self._update_attributes()
                self.async_write_ha_state()
                
                # Auch im Coordinator-Daten aktualisieren
                if hasattr(self.coordinator, 'data') and 'all_media' in self.coordinator.data:
                    for media in self.coordinator.data['all_media']:
                        if media.get('media_id') == media_id:
                            media["renewal_date"] = result.get("renewal_date", "")
                            media["renewal_date_iso"] = result.get("renewal_date_iso")
                            _LOGGER.debug(f"Updated renewal date in coordinator data for {media_id}")
                            break
            
            # Zeige dem Benutzer die Fehlermeldung
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "BibKat - Verlängerung nicht möglich",
                    "message": f"Verlängerung von '{media_title}' fehlgeschlagen:\n\n{message}",
                    "notification_id": f"bibkat_not_renewable_{media_id}",
                }
            )
        # Der Coordinator wurde bereits in async_renew_media zum Refresh aufgefordert.
        # Ein manuelles Update hier ist nicht mehr nötig.