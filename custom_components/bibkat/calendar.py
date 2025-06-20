"""Calendar platform for BibKat - Shows due dates and renewal reminders."""
from __future__ import annotations

import logging
from datetime import datetime, date, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    OPT_CREATE_ACCOUNT_CALENDARS,
    DEFAULT_CREATE_ACCOUNT_CALENDARS,
)

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
    """Set up the calendar platform."""
    from .account_manager import AccountManager
    from .coordinator import BibKatMultiAccountCoordinator
    
    coordinator: BibKatMultiAccountCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    account_manager: AccountManager = hass.data[DOMAIN][config_entry.entry_id]["account_manager"]
    library_url: str = config_entry.data["library_url"]
    
    # Get library
    library: Optional[Library] = account_manager.get_library(library_url)
    if not library:
        _LOGGER.error("Library not found for URL: %s", library_url)
        return
    
    # Create calendar entities
    entities: List[CalendarEntity] = []
    
    # Combined calendar for all accounts
    entities.append(
        BibKatCalendar(
            coordinator=coordinator,
            library_name=library.name,
            library_id=library.id,
        )
    )
    
    # Individual calendar for each account (only if enabled in options)
    # For now, default to False to avoid duplicates
    create_account_calendars = config_entry.options.get(
        OPT_CREATE_ACCOUNT_CALENDARS, DEFAULT_CREATE_ACCOUNT_CALENDARS
    )
    
    if create_account_calendars:
        for account in library.accounts:
            entities.append(
                BibKatAccountCalendar(
                    coordinator=coordinator,
                    account_id=account.id,
                    account_name=account.display_name,
                    library_name=library.name,
                )
            )
    
    async_add_entities(entities, True)


class BibKatCalendar(CoordinatorEntity[BibKatMultiAccountCoordinator], CalendarEntity):
    """Calendar showing all due dates across accounts."""

    _attr_has_entity_name: bool = False
    _attr_icon: str = "mdi:calendar-book"

    def __init__(
        self,
        coordinator: "BibKatMultiAccountCoordinator",
        library_name: str,
        library_id: str,
    ) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        
        self._library_name: str = library_name
        self._library_id: str = library_id
        self._attr_unique_id: str = f"bibkat_{library_id}_calendar"
        self._attr_name: str = f"BibKat {library_name} Kalender"
        
        # Set device info
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, library_id)},
            name=f"BibKat {library_name}",
            manufacturer="BibKat",
            model="Bibliothek",
            configuration_url=coordinator.library_url,
        )

    @property
    def event(self) -> Optional[CalendarEvent]:
        """Return the next upcoming event."""
        events = self._get_events(datetime.now(), datetime.now() + timedelta(days=30))
        return events[0] if events else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return self._get_events(start_date, end_date)

    def _get_events(self, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Get all events in date range."""
        events: List[CalendarEvent] = []
        all_media: List[Dict[str, Any]] = self.coordinator.data.get("all_media", [])
        _LOGGER.debug(f"Calendar: Checking {len(all_media)} media items for events between {start_date} and {end_date}")
        
        # Track processed media to avoid duplicates
        processed_media_ids: set[str] = set()
        
        for media in all_media:
            # Skip if we've already processed this media ID
            media_id = media.get("media_id")
            if media_id and media_id in processed_media_ids:
                _LOGGER.debug(f"Skipping duplicate media: {media.get('title')} (ID: {media_id})")
                continue
            
            if media_id:
                processed_media_ids.add(media_id)
            # Due date event
            due_date_iso: Optional[str] = media.get("due_date_iso")
            if due_date_iso:
                due_date = datetime.fromisoformat(due_date_iso).replace(hour=23, minute=59)
                
                # Make datetime timezone-aware if needed
                if start_date.tzinfo is not None and due_date.tzinfo is None:
                    due_date = due_date.replace(tzinfo=start_date.tzinfo)
                
                if start_date <= due_date <= end_date:
                    days_remaining: int = media.get("days_remaining", 0)
                    
                    # Event title with emoji based on urgency
                    if days_remaining < 0:
                        title = f"⚠️ ÜBERFÄLLIG: {media['title']}"
                        description = f"Dieses Buch ist seit {abs(days_remaining)} Tagen überfällig!"
                    elif days_remaining == 0:
                        title = f"🔴 HEUTE fällig: {media['title']}"
                        description = "Dieses Buch muss heute zurückgegeben werden!"
                    elif days_remaining <= 3:
                        title = f"⏰ Fällig: {media['title']}"
                        description = f"Rückgabe in {days_remaining} Tagen"
                    else:
                        title = f"📚 Fällig: {media['title']}"
                        description = f"Rückgabe in {days_remaining} Tagen"
                    
                    # Add account info
                    description += f"\n\nKonto: {media.get('account_alias', 'Unbekannt')}"
                    description += f"\nAutor: {media.get('author', 'Unbekannt')}"
                    
                    if media.get("renewable"):
                        if media.get("is_renewable_now"):
                            description += "\n\n✅ Kann jetzt verlängert werden"
                        else:
                            renewal_date = media.get("renewal_date", "")
                            description += f"\n\n⏳ Verlängerbar ab: {renewal_date}"
                    else:
                        description += "\n\n❌ Nicht verlängerbar"
                    
                    events.append(
                        CalendarEvent(
                            summary=title,
                            start=due_date.date(),
                            end=due_date.date() + timedelta(days=1),
                            description=description,
                            location=self._library_name,
                        )
                    )
            
            # Renewal reminder event (3 days before due date if renewable)
            if media.get("renewable") and due_date_iso:
                due_date = datetime.fromisoformat(due_date_iso)
                reminder_date = due_date - timedelta(days=3)
                
                # Make datetime timezone-aware if needed
                if start_date.tzinfo is not None and reminder_date.tzinfo is None:
                    reminder_date = reminder_date.replace(tzinfo=start_date.tzinfo)
                
                if start_date <= reminder_date <= end_date:
                    events.append(
                        CalendarEvent(
                            summary=f"🔔 Verlängerung prüfen: {media['title']}",
                            start=reminder_date.date(),
                            end=reminder_date.date() + timedelta(days=1),
                            description=f"Dieses Buch kann bald verlängert werden.\n\nKonto: {media.get('account_alias', 'Unbekannt')}",
                            location=self._library_name,
                        )
                    )
        
        # Sort by date
        events.sort(key=lambda x: x.start)
        return events


class BibKatAccountCalendar(CoordinatorEntity[BibKatMultiAccountCoordinator], CalendarEntity):
    """Calendar for a specific account."""

    _attr_has_entity_name: bool = False
    _attr_icon: str = "mdi:calendar-account"

    def __init__(
        self,
        coordinator: "BibKatMultiAccountCoordinator",
        account_id: str,
        account_name: str,
        library_name: str,
    ) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        
        self._account_id: str = account_id
        self._account_name: str = account_name
        self._library_name: str = library_name
        self._attr_unique_id: str = f"bibkat_{account_id}_calendar"
        self._attr_name: str = f"BibKat {library_name} {account_name} Kalender"
        
        # Set device info
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, account_id)},
            name=f"{library_name} - {account_name}",
            manufacturer="BibKat",
            model="Bibliothekskonto",
        )

    @property
    def event(self) -> Optional[CalendarEvent]:
        """Return the next upcoming event."""
        events = self._get_events(datetime.now(), datetime.now() + timedelta(days=30))
        return events[0] if events else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return self._get_events(start_date, end_date)

    def _get_events(self, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Get all events in date range for this account."""
        events: List[CalendarEvent] = []
        account_data: Dict[str, Any] = self.coordinator.data.get("accounts", {}).get(self._account_id, {})
        media_list: List[Dict[str, Any]] = account_data.get("borrowed_media", [])
        
        for media in media_list:
            # Due date event
            due_date_iso: Optional[str] = media.get("due_date_iso")
            if due_date_iso:
                due_date = datetime.fromisoformat(due_date_iso).replace(hour=23, minute=59)
                
                # Make datetime timezone-aware if needed
                if start_date.tzinfo is not None and due_date.tzinfo is None:
                    due_date = due_date.replace(tzinfo=start_date.tzinfo)
                
                if start_date <= due_date <= end_date:
                    days_remaining: int = media.get("days_remaining", 0)
                    
                    # Event title based on urgency
                    if days_remaining < 0:
                        title = f"⚠️ ÜBERFÄLLIG: {media['title']}"
                    elif days_remaining == 0:
                        title = f"🔴 HEUTE: {media['title']}"
                    elif days_remaining <= 3:
                        title = f"⏰ {media['title']}"
                    else:
                        title = f"📚 {media['title']}"
                    
                    description = f"Autor: {media.get('author', 'Unbekannt')}"
                    description += f"\nRückgabe in {days_remaining} Tagen"
                    
                    if media.get("renewable"):
                        if media.get("is_renewable_now"):
                            description += "\n\n✅ Kann jetzt verlängert werden"
                        else:
                            description += f"\n\n⏳ Noch nicht verlängerbar"
                    
                    events.append(
                        CalendarEvent(
                            summary=title,
                            start=due_date.date(),
                            end=due_date.date() + timedelta(days=1),
                            description=description,
                            location=self._library_name,
                        )
                    )
        
        # Sort by date
        events.sort(key=lambda x: x.start)
        return events