"""Handle notification actions for BibKat integration."""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ACTION_RECEIVED = f"{DOMAIN}_notification_action"


class NotificationActionHandler:
    """Handle actions from notifications."""
    
    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize notification action handler."""
        self.hass = hass
        self._listeners = []
        
    async def async_setup(self) -> None:
        """Set up notification action handling."""
        # Register mobile app notification action handler
        async def handle_mobile_app_notification_action(event):
            """Handle notification action from mobile app."""
            action = event.data.get("action")
            if not action:
                return
                
            # Check if this is a BibKat action
            if action.startswith("renew_all_"):
                entry_id = action.replace("renew_all_", "")
                await self._handle_renew_all_action(entry_id)
            elif action.startswith("renew_overdue_"):
                entry_id = action.replace("renew_overdue_", "")
                await self._handle_renew_overdue_action(entry_id)
            elif action.startswith("renew_account_"):
                account_id = action.replace("renew_account_", "")
                await self._handle_renew_account_action(account_id)
            elif action.startswith("renew_item_"):
                media_id = action.replace("renew_item_", "")
                await self._handle_renew_item_action(media_id)
            elif action.startswith("view_media_") or action.startswith("view_overdue_"):
                # This is handled by the URI in the notification
                pass
        
        # Listen for mobile app notification actions
        self.hass.bus.async_listen(
            "mobile_app_notification_action",
            handle_mobile_app_notification_action
        )
        
        # Webhook registration removed - not needed for notification actions
        # Mobile app notifications already work via events
        
        _LOGGER.debug("Notification action handler set up")
    
    async def async_stop(self) -> None:
        """Stop notification action handling."""
        # Remove listeners
        for unsub in self._listeners:
            unsub()
        self._listeners.clear()
    
    async def _handle_renew_all_action(self, entry_id: str) -> None:
        """Handle renew all action."""
        _LOGGER.info(f"Handling renew all action for entry {entry_id}")
        
        # Get the coordinator for this entry
        entry_data = self.hass.data[DOMAIN].get(entry_id)
        if not entry_data or "coordinator" not in entry_data:
            _LOGGER.error(f"No coordinator found for entry {entry_id}")
            return
        
        coordinator = entry_data["coordinator"]
        notification_manager = self.hass.data[DOMAIN].get("notification_manager")
        
        # Get renewable items
        all_media = coordinator.data.get("all_media", [])
        renewable_items = [
            item for item in all_media 
            if item.get("renewable") and item.get("is_renewable_now", False)
        ]
        
        if not renewable_items:
            # No items to renew
            await self._send_feedback_notification(
                "Keine Medien zum Verlängern",
                "Es gibt aktuell keine Medien, die verlängert werden können.",
                "book-cancel"
            )
            return
        
        # Call the renew service
        try:
            result = await coordinator.async_renew_all_media()
            
            # Send renewal result notification
            if notification_manager:
                await notification_manager.send_renewal_notification(
                    coordinator.library_url,
                    result
                )
        except Exception as e:
            _LOGGER.error(f"Error during renewal: {e}")
            await self._send_feedback_notification(
                "Fehler bei Verlängerung",
                f"Die Verlängerung konnte nicht durchgeführt werden: {str(e)}",
                "alert-circle"
            )
    
    async def _handle_renew_account_action(self, account_id: str) -> None:
        """Handle renew account action."""
        _LOGGER.info(f"Handling renew account action for account {account_id}")
        
        # Find the coordinator that has this account
        coordinator = None
        for entry_id, entry_data in self.hass.data[DOMAIN].items():
            if isinstance(entry_data, dict) and "coordinator" in entry_data:
                coord = entry_data["coordinator"]
                if account_id in coord.data.get("accounts", {}):
                    coordinator = coord
                    break
        
        if not coordinator:
            _LOGGER.error(f"No coordinator found for account {account_id}")
            return
        
        notification_manager = self.hass.data[DOMAIN].get("notification_manager")
        
        # Call the renew service for specific account
        try:
            result = await coordinator.async_renew_all_media(account_id)
            
            # Send renewal result notification
            if notification_manager:
                await notification_manager.send_renewal_notification(
                    coordinator.library_url,
                    result
                )
        except Exception as e:
            _LOGGER.error(f"Error during renewal: {e}")
            await self._send_feedback_notification(
                "Fehler bei Verlängerung",
                f"Die Verlängerung konnte nicht durchgeführt werden: {str(e)}",
                "alert-circle"
            )
    
    async def _handle_renew_overdue_action(self, entry_id: str) -> None:
        """Handle renew overdue items action."""
        _LOGGER.info(f"Handling renew overdue action for entry {entry_id}")
        
        # Get the coordinator for this entry
        entry_data = self.hass.data[DOMAIN].get(entry_id)
        if not entry_data or "coordinator" not in entry_data:
            _LOGGER.error(f"No coordinator found for entry {entry_id}")
            return
        
        coordinator = entry_data["coordinator"]
        notification_manager = self.hass.data[DOMAIN].get("notification_manager")
        
        # Get overdue renewable items
        all_media = coordinator.data.get("all_media", [])
        overdue_renewable = []
        
        for item in all_media:
            if item.get("days_remaining", 999) <= 0 and item.get("renewable", False):
                # Check if actually overdue
                due_date_iso = item.get("due_date_iso")
                if due_date_iso:
                    from datetime import date
                    due_date = date.fromisoformat(due_date_iso)
                    if due_date < date.today():
                        overdue_renewable.append(item)
        
        if not overdue_renewable:
            await self._send_feedback_notification(
                "Keine überfälligen Medien",
                "Es gibt keine überfälligen Medien, die verlängert werden können.",
                "book-cancel"
            )
            return
        
        # Call the renew service
        try:
            result = await coordinator.async_renew_all_media()
            
            # Send renewal result notification
            if notification_manager:
                await notification_manager.send_renewal_notification(
                    coordinator.library_url,
                    result
                )
        except Exception as e:
            _LOGGER.error(f"Error during renewal: {e}")
            await self._send_feedback_notification(
                "Fehler bei Verlängerung",
                f"Die Verlängerung konnte nicht durchgeführt werden: {str(e)}",
                "alert-circle"
            )
    
    async def _handle_renew_item_action(self, media_id: str) -> None:
        """Handle renew single item action."""
        _LOGGER.info(f"Handling renew item action for media {media_id}")
        
        # Find the coordinator and account that has this media
        coordinator = None
        account_id = None
        media_item = None
        
        for entry_id, entry_data in self.hass.data[DOMAIN].items():
            if isinstance(entry_data, dict) and "coordinator" in entry_data:
                coord = entry_data["coordinator"]
                all_media = coord.data.get("all_media", [])
                for media in all_media:
                    if media.get("media_id") == media_id:
                        coordinator = coord
                        account_id = media.get("account_id")
                        media_item = media
                        break
                if coordinator:
                    break
        
        if not coordinator or not account_id or not media_item:
            _LOGGER.error(f"No media found with ID {media_id}")
            await self._send_feedback_notification(
                "Medium nicht gefunden",
                f"Das Medium mit ID {media_id} wurde nicht gefunden.",
                "book-cancel"
            )
            return
        
        # Get the API for this account
        if account_id not in coordinator.apis:
            _LOGGER.error(f"No API instance for account {account_id}")
            return
        
        api = coordinator.apis[account_id]
        notification_manager = self.hass.data[DOMAIN].get("notification_manager")
        
        try:
            # Renew the specific media
            _LOGGER.info(
                "Renewing '%s' (ID: %s)",
                media_item.get("title", "Unknown"),
                media_id
            )
            
            # Call the API method to renew single media
            result = await api._renew_single_media(media_id)
            
            if result.get("success"):
                _LOGGER.info("Successfully renewed '%s'", media_item.get("title", "Unknown"))
                
                # Create a result object for notification
                renewal_result = {
                    "success": True,
                    "renewed": 1,
                    "failed": 0,
                    "message": f"'{media_item.get('title', 'Unknown')}' wurde erfolgreich verlängert",
                    "messages": [f"✅ {media_item.get('title', 'Unknown')}: Verlängert"],
                }
            else:
                error_msg = result.get("message", "Unknown error")
                _LOGGER.error("Failed to renew '%s': %s", media_item.get("title", "Unknown"), error_msg)
                
                renewal_result = {
                    "success": False,
                    "renewed": 0,
                    "failed": 1,
                    "message": f"Verlängerung von '{media_item.get('title', 'Unknown')}' fehlgeschlagen",
                    "errors": [f"❌ {media_item.get('title', 'Unknown')}: {error_msg}"],
                }
            
            # Send renewal result notification
            if notification_manager:
                await notification_manager.send_renewal_notification(
                    coordinator.library_url,
                    renewal_result
                )
                
            # Refresh coordinator data
            await coordinator.async_request_refresh()
            
        except Exception as e:
            _LOGGER.error(
                "Error renewing '%s': %s",
                media_item.get("title", "Unknown"),
                e
            )
            await self._send_feedback_notification(
                "Fehler bei Verlängerung",
                f"Die Verlängerung von '{media_item.get('title', 'Unknown')}' konnte nicht durchgeführt werden: {str(e)}",
                "alert-circle"
            )
    
    async def _send_feedback_notification(
        self,
        title: str,
        message: str,
        icon: str = "information",
    ) -> None:
        """Send a feedback notification."""
        # Use persistent notification as fallback
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"BibKat: {title}",
                "message": message,
                "notification_id": f"bibkat_feedback_{icon}",
            },
            blocking=False,
        )
