"""Account management for BibKat integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from dataclasses import dataclass, field

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store

from .const import DOMAIN

if TYPE_CHECKING:
    from .api import BibKatAPI

_LOGGER: logging.Logger = logging.getLogger(__name__)

STORAGE_VERSION: int = 1
STORAGE_KEY: str = f"{DOMAIN}_accounts"


@dataclass
class Account:
    """Represents a single library account."""
    
    username: str
    password: str
    alias: str = ""
    library_url: str = ""
    enabled: bool = True
    
    @property
    def id(self) -> str:
        """Generate unique ID for account."""
        library_name = self.library_url.rstrip('/').split('/')[-1] if self.library_url else "unknown"
        return f"{library_name}_{self.username}"
    
    @property
    def display_name(self) -> str:
        """Get display name for account."""
        if self.alias:
            return self.alias
        # TODO: In future, this could use Home Assistant's translation system
        # to support "Reader {username}" in English. For now, we keep the German default
        # as this is a German library system.
        return f"Leser {self.username}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "username": self.username,
            "password": self.password,
            "alias": self.alias,
            "library_url": self.library_url,
            "enabled": self.enabled,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Account:
        """Create from dictionary."""
        return cls(
            username=data["username"],
            password=data["password"],
            alias=data.get("alias", ""),
            library_url=data.get("library_url", ""),
            enabled=data.get("enabled", True),
        )


@dataclass
class Library:
    """Represents a library with multiple accounts."""
    
    url: str
    name: str
    accounts: List[Account] = field(default_factory=list)
    
    @property
    def id(self) -> str:
        """Generate unique ID for library."""
        return self.url.rstrip('/').split('/')[-1] if self.url else "unknown"
    
    def add_account(self, account: Account) -> None:
        """Add an account to this library."""
        account.library_url = self.url
        # Remove any existing account with same username
        self.accounts = [a for a in self.accounts if a.username != account.username]
        self.accounts.append(account)
    
    def remove_account(self, username: str) -> bool:
        """Remove an account by username."""
        original_count = len(self.accounts)
        self.accounts = [a for a in self.accounts if a.username != username]
        return len(self.accounts) < original_count
    
    def get_account(self, username: str) -> Optional[Account]:
        """Get account by username."""
        for account in self.accounts:
            if account.username == username:
                return account
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "url": self.url,
            "name": self.name,
            "accounts": [account.to_dict() for account in self.accounts],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Library:
        """Create from dictionary."""
        library = cls(
            url=data["url"],
            name=data["name"],
        )
        for account_data in data.get("accounts", []):
            account = Account.from_dict(account_data)
            library.add_account(account)
        return library


class AccountManager:
    """Manages multiple accounts across libraries."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize account manager."""
        self.hass: HomeAssistant = hass
        self._store: Store[Dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._libraries: Dict[str, Library] = {}
        self._loaded: bool = False
    
    async def async_load(self) -> None:
        """Load accounts from storage."""
        if self._loaded:
            return
            
        data: Optional[Dict[str, Any]] = await self._store.async_load()
        if data:
            for library_data in data.get("libraries", []):
                library: Library = Library.from_dict(library_data)
                self._libraries[library.id] = library
        
        self._loaded = True
        _LOGGER.debug("Loaded %d libraries from storage", len(self._libraries))
    
    async def async_save(self) -> None:
        """Save accounts to storage."""
        data: Dict[str, Any] = {
            "libraries": [library.to_dict() for library in self._libraries.values()]
        }
        await self._store.async_save(data)
        _LOGGER.debug("Saved %d libraries to storage", len(self._libraries))
    
    def get_library(self, library_url: str) -> Optional[Library]:
        """Get library by URL."""
        library_id: str = library_url.rstrip('/').split('/')[-1]
        return self._libraries.get(library_id)
    
    def add_library(self, library_url: str, library_name: str) -> Library:
        """Add a new library."""
        library_id: str = library_url.rstrip('/').split('/')[-1]
        library: Library = Library(url=library_url, name=library_name)
        self._libraries[library_id] = library
        return library
    
    def remove_library(self, library_url: str) -> bool:
        """Remove a library and all its accounts."""
        library_id: str = library_url.rstrip('/').split('/')[-1]
        if library_id in self._libraries:
            del self._libraries[library_id]
            return True
        return False
    
    def get_all_accounts(self) -> List[Account]:
        """Get all accounts across all libraries."""
        accounts: List[Account] = []
        for library in self._libraries.values():
            accounts.extend(library.accounts)
        return accounts
    
    def get_accounts_for_library(self, library_url: str) -> List[Account]:
        """Get all accounts for a specific library."""
        library: Optional[Library] = self.get_library(library_url)
        if library:
            return library.accounts
        return []
    
    async def migrate_from_config_entry(self, config_entry_data: Dict[str, Any]) -> Optional[Library]:
        """Migrate from old single-account config entry."""
        # Extract library URL and credentials
        library_url: str = config_entry_data.get("library_url", "https://www.bibkat.de/boehl/")
        username: str = config_entry_data.get("username", "")
        password: str = config_entry_data.get("password", "")
        
        if not username or not password:
            return None
        
        # Extract library name from URL
        library_name: str = library_url.rstrip('/').split('/')[-1].capitalize()
        
        # Create or get library
        library: Optional[Library] = self.get_library(library_url)
        if not library:
            library = self.add_library(library_url, library_name)
        
        # Create account
        account: Account = Account(
            username=username,
            password=password,
            alias=f"Leser {username}",
            library_url=library_url,
        )
        
        # Add account to library
        library.add_account(account)
        
        # Save to storage
        await self.async_save()
        
        return library
    
    def create_device_info(self, library: Library) -> Dict[str, Any]:
        """Create device info for a library."""
        return {
            "identifiers": {(DOMAIN, library.id)},
            "name": f"BibKat {library.name}",
            "manufacturer": "BibKat",
            "model": "Library System",
            "configuration_url": library.url,
        }
    
    async def test_account(self, account: Account, session: aiohttp.ClientSession) -> bool:
        """Test if account credentials are valid."""
        from .auth_helper import BibKatAuthHelper
        from homeassistant.exceptions import ConfigEntryAuthFailed
        
        auth_helper = BibKatAuthHelper(self.hass, account.library_url)
        
        try:
            # Try to create authenticated session
            await auth_helper.async_get_authenticated_session(
                account.username,
                account.password
            )
            return True
        except ConfigEntryAuthFailed:
            return False
        except Exception as e:
            _LOGGER.error(f"Unexpected error testing account: {e}")
            return False