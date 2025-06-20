"""Notification management for BibKat integration."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .account_manager import AccountManager, Library
from .const import (
    DEFAULT_BALANCE_THRESHOLD,
    DEFAULT_DUE_SOON_DAYS,
    DOMAIN,
    OPT_BALANCE_THRESHOLD,
    OPT_DUE_SOON_DAYS,
    OPT_NOTIFICATION_SERVICE,
    OPT_NOTIFY_DUE_SOON,
    OPT_NOTIFY_HIGH_BALANCE,
    OPT_NOTIFY_OVERDUE,
    OPT_NOTIFY_RENEWAL,
)
from .templates import MessageTemplate

_LOGGER = logging.getLogger(__name__)


class NotificationManager:
    """Manages notifications for BibKat libraries."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        account_manager: AccountManager,
    ) -> None:
        """Initialize notification manager."""
        self.hass = hass
        self.account_manager = account_manager
        self._notification_history: Dict[str, List[str]] = {}
        self._check_interval_unsub = None
        
    async def async_setup(self) -> None:
        """Set up notification checks."""
        # Schedule periodic checks every 4 hours
        self._check_interval_unsub = async_track_time_interval(
            self.hass,
            self._async_check_notifications,
            timedelta(hours=4),
        )
        
        # Do initial check
        await self._async_check_notifications(None)
    
    async def async_stop(self) -> None:
        """Stop notification checks."""
        if self._check_interval_unsub:
            self._check_interval_unsub()
            self._check_interval_unsub = None
    
    async def _async_check_notifications(self, _: Any) -> None:
        """Check all libraries for notification conditions."""
        # Get all config entries for BibKat
        entries = self.hass.config_entries.async_entries(DOMAIN)
        
        for entry in entries:
            library_url = entry.data.get("library_url")
            if not library_url:
                continue
                
            # Get notification settings from options
            options = entry.options
            notification_service = options.get(OPT_NOTIFICATION_SERVICE)
            
            if not notification_service:
                continue  # No notification service configured
            
            # Get coordinator data
            entry_data = self.hass.data[DOMAIN].get(entry.entry_id)
            if not entry_data or "coordinator" not in entry_data:
                continue
                
            coordinator = entry_data["coordinator"]
            if not coordinator.last_update_success:
                continue
                
            # Check various notification conditions
            await self._check_due_soon(entry, coordinator.data, options)
            await self._check_overdue(entry, coordinator.data, options)
            await self._check_high_balance(entry, coordinator.data, options)
            await self._check_available_reservations(entry, coordinator.data, options)
    
    async def _check_due_soon(
        self,
        entry,
        coordinator_data: Dict[str, Any],
        options: Dict[str, Any],
    ) -> None:
        """Check for items due soon."""
        if not options.get(OPT_NOTIFY_DUE_SOON, True):
            return
            
        due_soon_days = options.get(OPT_DUE_SOON_DAYS, DEFAULT_DUE_SOON_DAYS)
        notification_service = options.get(OPT_NOTIFICATION_SERVICE)
        
        all_media = coordinator_data.get("all_media", [])
        due_soon_items = []
        
        for media in all_media:
            days_remaining = media.get("days_remaining", 999)
            if 0 < days_remaining <= due_soon_days:
                due_soon_items.append(media)
        
        if due_soon_items:
            # Build notification message using template
            library_name = entry.title.split(" - ")[0]
            library_url = entry.data.get("library_url")
            template = MessageTemplate("de")  # TODO: Get language from config
            title, message = template.format_due_soon(library_name, due_soon_items)
            
            # Check if we already sent this notification today
            notification_key = f"{entry.entry_id}_due_soon_{date.today()}"
            if notification_key not in self._notification_history.get(library_name, []):
                # Build actions based on renewable items
                actions = []
                
                # Check if any items are renewable now
                renewable_now = [item for item in due_soon_items if item.get('is_renewable_now', False)]
                renewable_soon = [item for item in due_soon_items if item.get('renewable', False) and not item.get('is_renewable_now', False)]
                
                if renewable_now:
                    # Add renew all action
                    actions.append({
                        "action": f"renew_all_{entry.entry_id}",
                        "title": f"📚 Alle {len(renewable_now)} verlängern",
                        "uri": f"homeassistant://navigate/lovelace/bibliothek"
                    })
                    
                    # If there are only a few renewable items, add individual actions
                    if len(renewable_now) <= 3:
                        for item in renewable_now:
                            actions.append({
                                "action": f"renew_item_{item.get('media_id', '')}",
                                "title": f"📖 {item.get('title', 'Unbekannt')[:30]}{'...' if len(item.get('title', '')) > 30 else ''}",
                            })
                    
                    # If multiple accounts involved, add per-account actions
                    accounts_with_renewable = {}
                    for item in renewable_now:
                        account_alias = item.get('account_alias', 'Unknown')
                        account_id = item.get('account_id', '')
                        if account_id and account_id not in accounts_with_renewable:
                            accounts_with_renewable[account_id] = account_alias
                    
                    if len(accounts_with_renewable) > 1 and len(renewable_now) > 3:
                        for account_id, account_alias in accounts_with_renewable.items():
                            count = len([i for i in renewable_now if i.get('account_id') == account_id])
                            actions.append({
                                "action": f"renew_account_{account_id}",
                                "title": f"📗 {account_alias} ({count})",
                            })
                elif renewable_soon:
                    # Add a reminder action for items that will be renewable soon
                    actions.append({
                        "action": f"view_renewable_soon_{entry.entry_id}",
                        "title": f"⏳ {len(renewable_soon)} bald verlängerbar",
                        "uri": f"homeassistant://navigate/lovelace/bibliothek"
                    })
                
                # Add view details action
                actions.append({
                    "action": f"view_media_{entry.entry_id}",
                    "title": "📖 Details anzeigen",
                    "uri": f"homeassistant://navigate/lovelace/bibliothek"
                })
                
                await self._send_notification(
                    notification_service,
                    title,
                    message,
                    "book-clock",
                    actions,
                )
                
                # Record notification
                if library_name not in self._notification_history:
                    self._notification_history[library_name] = []
                self._notification_history[library_name].append(notification_key)
    
    async def _check_overdue(
        self,
        entry,
        coordinator_data: Dict[str, Any],
        options: Dict[str, Any],
    ) -> None:
        """Check for overdue items."""
        if not options.get(OPT_NOTIFY_OVERDUE, True):
            return
            
        notification_service = options.get(OPT_NOTIFICATION_SERVICE)
        
        all_media = coordinator_data.get("all_media", [])
        overdue_items = []
        
        for media in all_media:
            days_remaining = media.get("days_remaining", 999)
            if days_remaining <= 0:
                # Check if actually overdue by looking at ISO date
                due_date_iso = media.get("due_date_iso")
                if due_date_iso:
                    due_date = date.fromisoformat(due_date_iso)
                    if due_date < date.today():
                        overdue_items.append(media)
        
        if overdue_items:
            # Build notification message using template
            library_name = entry.title.split(" - ")[0]
            template = MessageTemplate("de")  # TODO: Get language from config
            title, message = template.format_overdue(library_name, overdue_items)
            
            # Check if we already sent this notification today
            notification_key = f"{entry.entry_id}_overdue_{date.today()}"
            if notification_key not in self._notification_history.get(library_name, []):
                # Build actions
                actions = []
                
                # Check if any overdue items are renewable
                renewable_overdue = [item for item in overdue_items if item.get('renewable', False)]
                if renewable_overdue:
                    actions.append({
                        "action": f"renew_overdue_{entry.entry_id}",
                        "title": f"🔄 Versuche Verlängerung ({len(renewable_overdue)})",
                    })
                    
                    # If there are only a few renewable items, add individual actions
                    if len(renewable_overdue) <= 3:
                        for item in renewable_overdue:
                            actions.append({
                                "action": f"renew_item_{item.get('media_id', '')}",
                                "title": f"📖 {item.get('title', 'Unbekannt')[:30]}{'...' if len(item.get('title', '')) > 30 else ''}",
                            })
                
                # Add view in app action
                actions.append({
                    "action": f"view_overdue_{entry.entry_id}",
                    "title": "📱 In App öffnen",
                    "uri": f"homeassistant://navigate/lovelace/bibliothek"
                })
                
                await self._send_notification(
                    notification_service,
                    title,
                    message,
                    "alarm",
                    actions,
                )
                
                # Record notification
                if library_name not in self._notification_history:
                    self._notification_history[library_name] = []
                self._notification_history[library_name].append(notification_key)
    
    async def _check_high_balance(
        self,
        entry,
        coordinator_data: Dict[str, Any],
        options: Dict[str, Any],
    ) -> None:
        """Check for high account balances."""
        if not options.get(OPT_NOTIFY_HIGH_BALANCE, True):
            return
            
        notification_service = options.get(OPT_NOTIFICATION_SERVICE)
        balance_threshold = options.get(OPT_BALANCE_THRESHOLD, DEFAULT_BALANCE_THRESHOLD)
        
        accounts_data = coordinator_data.get("accounts", {})
        high_balance_accounts = []
        
        for account_id, account_data in accounts_data.items():
            balance_info = account_data.get("balance_info", {})
            balance = balance_info.get("balance", 0.0)
            
            if balance >= balance_threshold:
                # Get account alias
                library = self.account_manager.get_library(entry.data.get("library_url"))
                if library:
                    for account in library.accounts:
                        if account.id == account_id:
                            high_balance_accounts.append({
                                "alias": account.display_name,
                                "balance": balance,
                                "currency": balance_info.get("currency", "EUR"),
                            })
                            break
        
        if high_balance_accounts:
            # Build notification message using template
            library_name = entry.title.split(" - ")[0]
            template = MessageTemplate("de")  # TODO: Get language from config
            title, message = template.format_balance(
                library_name,
                high_balance_accounts,
                balance_threshold
            )
            
            # Check if we already sent this notification this week
            week_number = date.today().isocalendar()[1]
            notification_key = f"{entry.entry_id}_balance_{week_number}"
            if notification_key not in self._notification_history.get(library_name, []):
                await self._send_notification(
                    notification_service,
                    title,
                    message,
                    "finance",
                )
                
                # Record notification
                if library_name not in self._notification_history:
                    self._notification_history[library_name] = []
                self._notification_history[library_name].append(notification_key)
    
    async def send_renewal_notification(
        self,
        library_url: str,
        result: Dict[str, Any],
    ) -> None:
        """Send notification about renewal results."""
        # Find config entry for this library
        entry = None
        for e in self.hass.config_entries.async_entries(DOMAIN):
            if e.data.get("library_url") == library_url:
                entry = e
                break
        
        if not entry:
            return
        
        options = entry.options
        if not options.get(OPT_NOTIFY_RENEWAL, True):
            return
        
        notification_service = options.get(OPT_NOTIFICATION_SERVICE)
        if not notification_service:
            return
        
        # Build notification using template
        library_name = entry.title.split(" - ")[0]
        template = MessageTemplate("de")  # TODO: Get language from config
        title, message = template.format_renewal(library_name, result)
        
        icon = "book-check" if result.get("success") else "book-cancel"
        
        await self._send_notification(
            notification_service,
            title,
            message,
            icon,
        )
    
    async def test_notification(
        self,
        library_url: str,
    ) -> bool:
        """Send a test notification."""
        # Find config entry for this library
        entry = None
        for e in self.hass.config_entries.async_entries(DOMAIN):
            if e.data.get("library_url") == library_url:
                entry = e
                break
        
        if not entry:
            return False
        
        options = entry.options
        notification_service = options.get(OPT_NOTIFICATION_SERVICE)
        if not notification_service:
            return False
        
        library_name = entry.title.split(" - ")[0]
        template = MessageTemplate("de")  # TODO: Get language from config
        title, message = template.format_test(library_name)
        
        # Add test actions to demonstrate actionable notifications
        actions = [
            {
                "action": f"test_action_renew_{entry.entry_id}",
                "title": "📚 Test: Verlängerung",
            },
            {
                "action": f"test_action_view_{entry.entry_id}",
                "title": "📖 Test: Details anzeigen",
                "uri": f"homeassistant://navigate/lovelace/bibliothek"
            }
        ]
        
        await self._send_notification(
            notification_service,
            title,
            message,
            "bell",
            actions,
        )
        
        return True
    
    async def _check_available_reservations(
        self,
        entry,
        coordinator_data: Dict[str, Any],
        options: Dict[str, Any],
    ) -> None:
        """Check for reservations that are now available."""
        if not options.get(OPT_NOTIFICATION_SERVICE):
            return
        
        notification_service = options.get(OPT_NOTIFICATION_SERVICE)
        library_name = entry.title.split(" - ")[0]
        
        # Check all accounts for available reservations
        available_reservations = []
        
        for account_data in coordinator_data.get("accounts", {}).values():
            reservations = account_data.get("reservations", [])
            for reservation in reservations:
                # Check if position is 1 (available for pickup)
                if reservation.get("position") == 1:
                    available_reservations.append(reservation)
        
        if available_reservations:
            # Check if we already notified about these today
            notification_key = f"{entry.entry_id}_reservations_{date.today()}"
            if notification_key not in self._notification_history.get(library_name, []):
                # Build notification
                template = MessageTemplate("de")
                
                if len(available_reservations) == 1:
                    res = available_reservations[0]
                    title = f"📚 {library_name}: Vormerkung verfügbar!"
                    message = f"'{res.get('title', 'Unbekannt')}' kann abgeholt werden.\n"
                    message += f"Autor: {res.get('author', 'Unbekannt')}\n"
                    message += f"Zweigstelle: {res.get('branch', 'Unbekannt')}"
                else:
                    title = f"📚 {library_name}: {len(available_reservations)} Vormerkungen verfügbar!"
                    message = "Folgende Bücher können abgeholt werden:\n"
                    for res in available_reservations:
                        message += f"• {res.get('title', 'Unbekannt')}\n"
                
                # Add action to view in app
                actions = [{
                    "action": f"view_reservations_{entry.entry_id}",
                    "title": "📱 Vormerkungen anzeigen",
                    "uri": f"homeassistant://navigate/lovelace/bibliothek"
                }]
                
                await self._send_notification(
                    notification_service,
                    title,
                    message,
                    "book-check",
                    actions,
                )
                
                # Record notification
                if library_name not in self._notification_history:
                    self._notification_history[library_name] = []
                self._notification_history[library_name].append(notification_key)
    
    async def _send_notification(
        self,
        service_name: str,
        title: str,
        message: str,
        icon: str = "book",
        actions: List[Dict[str, Any]] = None,
    ) -> None:
        """Send a notification with optional actions."""
        try:
            # Parse service name
            try:
                domain, service = service_name.split(".", 1)
            except ValueError:
                _LOGGER.error(
                    f"Invalid notification service format: {service_name}. "
                    f"Expected 'domain.service_name' (e.g., 'notify.mobile_app_phone')"
                )
                return
            
            # Prepare service data
            service_data = {
                "title": title,
                "message": message,
                "data": {
                    "icon": f"mdi:{icon}",
                    "tag": f"bibkat_{title.lower().replace(' ', '_')}",
                    "importance": "default",
                    "channel": "BibKat",
                    "group": "bibkat_notifications",
                    "color": "#1976D2",
                },
            }
            
            # Add actions if provided
            if actions:
                service_data["data"]["actions"] = actions
            
            # Call notification service
            await self.hass.services.async_call(
                domain,
                service,
                service_data,
                blocking=False,
            )
            
            _LOGGER.debug(f"Sent notification via {service_name}: {title}")
            
        except Exception as e:
            _LOGGER.error(f"Failed to send notification: {e}")