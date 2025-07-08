"""Data update coordinator for BibKat with multi-account support."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

if TYPE_CHECKING:
    from .account_manager import Account, AccountManager
    from .api import BibKatAPI

_LOGGER: logging.Logger = logging.getLogger(__name__)


class BibKatMultiAccountCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching BibKat data for multiple accounts."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        account_manager: "AccountManager",
        library_url: str,
        renewal_rules_manager = None,
    ) -> None:
        """Initialize."""
        # Add random variation to update interval (±10%)
        base_interval = UPDATE_INTERVAL.total_seconds()
        randomized_seconds = base_interval + random.uniform(-base_interval * 0.1, base_interval * 0.1)
        randomized_interval = timedelta(seconds=randomized_seconds)
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{library_url.split('/')[-2]}",
            update_interval=randomized_interval,
        )
        self.config_entry: ConfigEntry = config_entry
        self.account_manager: "AccountManager" = account_manager
        self.library_url: str = library_url
        self.renewal_rules_manager = renewal_rules_manager
        self.apis: Dict[str, "BibKatAPI"] = {}
        
        _LOGGER.debug(
            "Coordinator initialized with randomized interval: %s (base: %s)",
            randomized_interval,
            UPDATE_INTERVAL
        )
        
    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from API for all accounts."""
        from .account_manager import Account
        from .api import BibKatAPI
        
        # Randomize next update interval for more human-like behavior
        base_interval = UPDATE_INTERVAL.total_seconds()
        randomized_seconds = base_interval + random.uniform(-base_interval * 0.15, base_interval * 0.15)
        self.update_interval = timedelta(seconds=randomized_seconds)
        _LOGGER.debug("Next update in %s", self.update_interval)
        
        # Get all accounts for this library
        accounts: List[Account] = self.account_manager.get_accounts_for_library(self.library_url)
        
        if not accounts:
            raise UpdateFailed("No accounts configured for this library")
        
        all_data: Dict[str, Any] = {
            "library_url": self.library_url,
            "accounts": {},
            "total_borrowed": 0,
            "all_media": [],
        }
        
        # Reset reservation fetch flag for each update
        self._reservations_fetched = False
        self._shared_reservations = {}
        
        # Fetch data for each account
        for i, account in enumerate(accounts):
            if not account.enabled:
                continue
                
            # Add random delay between accounts (0.5-2 seconds)
            if i > 0:
                delay = random.uniform(0.5, 2.0)
                _LOGGER.debug("Waiting %.1f seconds before next account", delay)
                await asyncio.sleep(delay)
                
            try:
                # Get or create API instance for this account
                if account.id not in self.apis:
                    from homeassistant.helpers.aiohttp_client import async_get_clientsession
                    
                    # Check if browser mode is enabled
                    from .const import OPT_USE_BROWSER, DEFAULT_USE_BROWSER
                    use_browser = self.config_entry.options.get(
                        OPT_USE_BROWSER, 
                        DEFAULT_USE_BROWSER
                    )
                    
                    self.apis[account.id] = BibKatAPI(
                        self.hass,
                        account.username,
                        account.password,
                        self.library_url,
                        account.id,
                        renewal_rules_manager=self.renewal_rules_manager,
                        use_browser=use_browser
                    )
                
                api: BibKatAPI = self.apis[account.id]
                
                # Ensure logged in (auth helper handles session management)
                if not await api._ensure_logged_in():
                    _LOGGER.error(
                        "Failed to login for account %s at %s",
                        account.username,
                        self.library_url
                    )
                    continue
                
                # Get borrowed media
                media: List[Dict[str, Any]] = await api.get_borrowed_media()
                _LOGGER.info(f"Account {account.username} has {len(media)} borrowed media items")
                
                # Log details of media items
                for idx, m in enumerate(media):
                    _LOGGER.debug(
                        f"Media {idx + 1} from account {account.username}: "
                        f"ID={m.get('media_id', 'NO_ID')}, "
                        f"Title='{m.get('title', 'NO_TITLE')}', "
                        f"Owner={m.get('owner_number', 'NONE')}, "
                        f"Found on={m.get('found_on', [])}"
                    )
                
                # Add account info to each media item
                for item in media:
                    # If this is from family page and has owner info, try to match to correct account
                    if item.get('owner_number') and 'family' in item.get('found_on', []):
                        owner_number = item.get('owner_number')
                        # Try to find the account with this number
                        owner_account = None
                        for acc in accounts:
                            if acc.username == owner_number:
                                owner_account = acc
                                break
                        
                        if owner_account:
                            item["account_id"] = owner_account.id
                            item["account_alias"] = owner_account.alias or f"Leser {owner_account.username}"
                            _LOGGER.debug(f"Media '{item.get('title', 'Unknown')}' assigned to owner account {owner_account.username} (ID: {owner_account.id})")
                        else:
                            # Owner not configured, use actual account number
                            item["account_id"] = owner_number  # Use real account number
                            # Use the owner_name from the page if available, otherwise default to "Leser"
                            # TODO: Could be internationalized in future
                            item["account_alias"] = item.get('owner_name', f"Leser {owner_number}")
                            item["is_configured"] = False  # Mark as unconfigured instead of external
                            _LOGGER.debug(f"Media '{item.get('title', 'Unknown')}' belongs to unconfigured family member {owner_number}")
                    else:
                        # Regular assignment (own media)
                        item["account_id"] = account.id
                        item["account_alias"] = account.alias or f"Leser {account.username}"
                        _LOGGER.debug(f"Media '{item.get('title', 'Unknown')}' assigned to account {account.username} (ID: {account.id})")
                
                # Get balance info
                balance_info: Dict[str, Any] = await api.get_account_info()
                
                # Get reservations (if API supports it)
                reservations: List[Dict[str, Any]] = []
                if hasattr(api, 'get_reserved_media'):
                    try:
                        # Only fetch reservations once per update cycle
                        # The API already checks both main and family pages
                        if not self._reservations_fetched:
                            self._reservations_fetched = True
                            all_reservations = await api.get_reserved_media()
                            _LOGGER.info(f"Fetched {len(all_reservations)} reservations from API")
                            
                            # Process reservations and assign to correct accounts
                            for item in all_reservations:
                                # If owner_number is present, try to match to account
                                owner_number = item.get('owner_number')
                                if owner_number:
                                    # Find account with this username
                                    assigned = False
                                    for acc in accounts:
                                        if acc.username == owner_number:
                                            if acc.id not in self._shared_reservations:
                                                self._shared_reservations[acc.id] = []
                                            item["account_id"] = acc.id
                                            item["account_alias"] = acc.alias or f"Leser {acc.username}"
                                            self._shared_reservations[acc.id].append(item)
                                            assigned = True
                                            _LOGGER.debug(f"Assigned reservation '{item.get('title', 'Unknown')}' to account {acc.username}")
                                            break
                                    
                                    if not assigned:
                                        # Unconfigured family member - use real account number
                                        if owner_number not in self._shared_reservations:
                                            self._shared_reservations[owner_number] = []
                                        item["account_id"] = owner_number  # Use real account number
                                        item["account_alias"] = item.get('owner_name', f"Leser {owner_number}")
                                        item["is_configured"] = False  # Mark as unconfigured
                                        self._shared_reservations[owner_number].append(item)
                                        _LOGGER.debug(f"Assigned reservation '{item.get('title', 'Unknown')}' to unconfigured member {owner_number}")
                                else:
                                    # No owner info, assign to current account
                                    if account.id not in self._shared_reservations:
                                        self._shared_reservations[account.id] = []
                                    item["account_id"] = account.id
                                    item["account_alias"] = account.alias or f"Leser {account.username}"
                                    self._shared_reservations[account.id].append(item)
                        
                        # Always get reservations for this account from shared storage
                        reservations = self._shared_reservations.get(account.id, [])
                        _LOGGER.info(f"Account {account.username} has {len(reservations)} reservations assigned")
                    except Exception as e:
                        _LOGGER.error("Error fetching reservations: %s", e, exc_info=True)
                
                # Store account data
                account_data: Dict[str, Any] = {
                    "borrowed_media": media,
                    "total_borrowed": len(media),
                    "balance_info": balance_info,
                    "reservations": reservations,
                    "total_reservations": len(reservations),
                    "last_update": self.last_update_success_time if hasattr(self, 'last_update_success_time') else None,
                }
                
                all_data["accounts"][account.id] = account_data
                all_data["total_borrowed"] += len(media)
                all_data["all_media"].extend(media)
                
            except Exception as e:
                _LOGGER.error(
                    "Error fetching data for account %s: %s",
                    account.username,
                    e
                )
                continue
        
        # Add unconfigured family members to the data
        # First, find all unique unconfigured account numbers from media and reservations
        unconfigured_accounts = set()
        
        # From media items
        for media in all_data["all_media"]:
            if not media.get("is_configured", True):  # Default True for backward compatibility
                account_id = media.get("account_id")
                if account_id and not account_id.startswith("external_"):
                    unconfigured_accounts.add(account_id)
                    
        # From reservations
        for account_number, reservations in self._shared_reservations.items():
            # Check if this is an unconfigured account
            is_configured = False
            for acc in accounts:
                if acc.username == account_number or acc.id == account_number:
                    is_configured = True
                    break
            if not is_configured and not account_number.startswith("external_"):
                unconfigured_accounts.add(account_number)
                
        # Create account entries for all unconfigured family members
        for account_number in unconfigured_accounts:
            # Collect borrowed media for this account
            borrowed_media = [m for m in all_data["all_media"] 
                            if m.get("account_id") == account_number]
            
            # Get reservations for this account
            reservations = self._shared_reservations.get(account_number, [])
            
            # Create account entry
            all_data["accounts"][account_number] = {
                "borrowed_media": borrowed_media,
                "total_borrowed": len(borrowed_media),
                "balance_info": {},
                "reservations": reservations,
                "total_reservations": len(reservations),
                "last_update": None,
                "is_configured": False,  # Mark as unconfigured
                "account_number": account_number,
                "account_alias": f"Leser {account_number}",  # Default alias
            }
            _LOGGER.info(
                f"Added unconfigured account {account_number}: "
                f"{len(borrowed_media)} media, {len(reservations)} reservations"
            )
        
        # Sort all media by days remaining
        all_data["all_media"].sort(key=lambda x: x.get("days_remaining", 999))
        
        # Check if we should fetch renewal dates for non-renewable items
        # Do this once per day to avoid too many requests
        should_fetch_renewal_dates = False
        if not hasattr(self, '_last_renewal_date_fetch'):
            self._last_renewal_date_fetch = None
            
        if self._last_renewal_date_fetch is None or \
           (datetime.now() - self._last_renewal_date_fetch).total_seconds() > 86400:  # 24 hours
            should_fetch_renewal_dates = True
            self._last_renewal_date_fetch = datetime.now()
            _LOGGER.info("Performing daily renewal date check for non-renewable items")
            
        if should_fetch_renewal_dates:
            # Get renewal dates for non-renewable items
            for account_data in all_data["accounts"].values():
                for media in account_data.get("borrowed_media", []):
                    # Only check items that are not renewable and don't have a renewal date
                    if not media.get("renewable") and not media.get("renewal_date_iso"):
                        media_id = media.get("media_id")
                        if media_id:
                            _LOGGER.debug(f"Checking renewal date for non-renewable item: {media.get('title', 'Unknown')}")
                            
                            # Use the renew method to get the date from error message
                            try:
                                result = await self.async_renew_media(media_id)
                                if result and not result.get("success") and result.get("renewal_date_iso"):
                                    renewal_date = result.get("renewal_date", "")
                                    renewal_date_iso = result["renewal_date_iso"]
                                    
                                    # Update this media item
                                    media["renewal_date"] = renewal_date
                                    media["renewal_date_iso"] = renewal_date_iso
                                    
                                    # Propagate to all media items with the same ID
                                    for acc_data in all_data["accounts"].values():
                                        for m in acc_data.get("borrowed_media", []):
                                            if m.get("media_id") == media_id:
                                                m["renewal_date"] = renewal_date
                                                m["renewal_date_iso"] = renewal_date_iso
                                    
                                    # Also update in all_media list
                                    for m in all_data["all_media"]:
                                        if m.get("media_id") == media_id:
                                            m["renewal_date"] = renewal_date
                                            m["renewal_date_iso"] = renewal_date_iso
                                    
                                    _LOGGER.info(
                                        f"Got renewal date for {media.get('title', 'Unknown')}: "
                                        f"{media['renewal_date']} (propagated to all instances)"
                                    )
                                    
                                # Small delay to avoid rate limiting
                                await asyncio.sleep(random.uniform(0.5, 1.5))
                            except Exception as e:
                                _LOGGER.error(f"Error getting renewal date for {media_id}: {e}", exc_info=True)
        
        _LOGGER.info(
            f"Coordinator update complete: Total {all_data['total_borrowed']} media items, "
            f"{len(all_data['all_media'])} in all_media list"
        )
        
        # Log final media list
        for idx, media in enumerate(all_data["all_media"]):
            _LOGGER.debug(
                f"Final media {idx + 1}: ID={media.get('media_id', 'NO_ID')}, "
                f"Title='{media.get('title', 'NO_TITLE')}', "
                f"Account={media.get('account_id', 'NO_ACCOUNT')}, "
                f"External={media.get('external_account', False)}"
            )
        
        return all_data
    
    async def async_renew_all_media(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """Renew all renewable media for one or all accounts."""
        from .account_manager import Account
        from .api import BibKatAPI
        
        result: Dict[str, Any] = {
            "success": True,
            "renewed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
            "messages": [],
        }
        
        # Determine which accounts to process
        if account_id:
            accounts: List[Account] = [
                acc for acc in self.account_manager.get_accounts_for_library(self.library_url)
                if acc.id == account_id
            ]
        else:
            accounts = self.account_manager.get_accounts_for_library(self.library_url)
        
        # Process each account
        for account in accounts:
            if not account.enabled or account.id not in self.apis:
                continue
                
            api: BibKatAPI = self.apis[account.id]
            # Auth helper handles session management automatically
            
            try:
                account_result: Dict[str, Any] = await api.renew_all_media()
                
                # Aggregate results
                result["renewed"] += account_result.get("renewed", 0)
                result["failed"] += account_result.get("failed", 0)
                result["skipped"] += account_result.get("skipped", 0)
                
                # Add account prefix to messages
                prefix: str = f"[{account.display_name}] "
                if account_result.get("errors"):
                    result["errors"].extend([prefix + err for err in account_result["errors"]])
                if account_result.get("messages"):
                    result["messages"].extend([prefix + msg for msg in account_result["messages"]])
                    
            except Exception as e:
                result["failed"] += 1
                result["errors"].append(f"[{account.display_name}] Fehler: {str(e)}")
        
        # Update success status
        result["success"] = result["failed"] == 0
        
        # Build summary message
        parts = []
        if result["renewed"] > 0:
            parts.append(f"{result['renewed']} verlängert")
        if result["skipped"] > 0:
            parts.append(f"{result['skipped']} noch nicht verlängerbar")
        if result["failed"] > 0:
            parts.append(f"{result['failed']} fehlgeschlagen")
            
        if parts:
            result["message"] = "Ergebnis: " + ", ".join(parts)
        else:
            result["message"] = "Keine verlängerbaren Medien gefunden"
        
        # Trigger data update
        await self.async_request_refresh()
        
        return result
    
    async def async_renew_media(self, media_id: str, account_id: Optional[str] = None) -> Dict[str, Any]:
        """Renew a specific media item."""
        from .api import BibKatAPI
        
        result: Dict[str, Any] = {
            "success": False,
            "media_id": media_id,
            "title": "",
            "message": "",
        }
        
        # Find the media item in our data
        media_found = None
        owner_account_id = None
        
        for acc_id, account_data in self.data.get("accounts", {}).items():
            for media in account_data.get("borrowed_media", []):
                if media.get("media_id") == media_id:
                    media_found = media
                    owner_account_id = acc_id
                    break
            if media_found:
                break
        
        if not media_found:
            result["message"] = f"Medium mit ID {media_id} nicht gefunden"
            return result
        
        result["title"] = media_found.get("title", "")
        
        # If account_id provided, verify it matches
        if account_id and account_id != owner_account_id:
            result["message"] = f"Medium gehört nicht zu Konto {account_id}"
            return result
        
        # Family members can be renewed through the family page
        # Even if they're marked as external, we can still renew them
        
        # Get the API for this account
        # For unconfigured accounts, use any available API (they all use the family page)
        api: Optional[BibKatAPI] = None
        
        # Check if this is a configured account
        is_configured = False
        for account in self.account_manager.get_accounts_for_library(self.library_url):
            if account.id == owner_account_id or account.username == owner_account_id:
                is_configured = True
                api = self.apis.get(account.id)
                break
                
        if not is_configured:
            # For unconfigured accounts, use any logged-in API
            for api_instance in self.apis.values():
                if api_instance.logged_in:
                    api = api_instance
                    _LOGGER.info(f"Using API from any logged-in account to renew unconfigured account {owner_account_id}'s media")
                    break
            
        if not api:
            result["message"] = f"Keine API-Verbindung verfügbar"
            return result
        
        # Try to renew the media
        try:
            _LOGGER.info(f"Calling api.renew_media for media_id: {media_id}")
            renew_result = await api.renew_media(media_id)
            _LOGGER.info(f"API renewal result: {renew_result}")
            
            if renew_result.get("success"):
                result["success"] = True
                result["new_due_date"] = renew_result.get("new_due_date", "")
                result["message"] = f"Erfolgreich verlängert bis {result['new_due_date']}"
            else:
                result["message"] = renew_result.get("message", "Verlängerung fehlgeschlagen")
                if renew_result.get("renewal_date"):
                    result["renewal_date"] = renew_result["renewal_date"]
                    result["message"] += f". Verlängerbar ab {result['renewal_date']}"
                if renew_result.get("renewal_date_iso"):
                    result["renewal_date_iso"] = renew_result["renewal_date_iso"]
            
        except Exception as e:
            _LOGGER.error("Error renewing media %s: %s", media_id, e)
            result["message"] = f"Fehler bei der Verlängerung: {str(e)}"
        
        # Trigger data update
        await self.async_request_refresh()
        
        return result