"""Authentication helper for BibKat using HA patterns."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from aiohttp import ClientSession, CookieJar
from bs4 import BeautifulSoup

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
AUTH_STORAGE_KEY = f"{DOMAIN}_auth"
SESSION_TIMEOUT = timedelta(hours=1)  # BibKat sessions typically expire after 1 hour


class BibKatAuthHelper:
    """Helper for BibKat authentication with HA patterns."""
    
    def __init__(self, hass: HomeAssistant, library_url: str):
        """Initialize the auth helper."""
        self.hass = hass
        self.library_url = library_url.rstrip('/')
        
        # Use HA's encrypted storage
        self._credential_store = Store(
            hass,
            STORAGE_VERSION,
            f"{AUTH_STORAGE_KEY}_credentials",
            private=True,  # Enables encryption
            atomic_writes=True
        )
        
        # Session cache store
        self._session_store = Store(
            hass,
            STORAGE_VERSION,
            f"{AUTH_STORAGE_KEY}_sessions",
            private=False,  # Session data, not credentials
            atomic_writes=True
        )
        
        self._sessions: Dict[str, Dict[str, Any]] = {}
        
    async def async_save_credentials(self, username: str, password: str, account_id: str) -> None:
        """Save encrypted credentials."""
        data = await self._credential_store.async_load() or {}
        
        data[account_id] = {
            "username": username,
            "password": password,
            "library_url": self.library_url,
            "created_at": datetime.now().isoformat(),
        }
        
        await self._credential_store.async_save(data)
        _LOGGER.debug(f"Saved credentials for account {account_id}")
        
    async def async_get_credentials(self, account_id: str) -> Optional[Dict[str, str]]:
        """Get credentials for an account."""
        data = await self._credential_store.async_load() or {}
        return data.get(account_id)
        
    async def async_remove_credentials(self, account_id: str) -> None:
        """Remove credentials for an account."""
        data = await self._credential_store.async_load() or {}
        if account_id in data:
            del data[account_id]
            await self._credential_store.async_save(data)
            _LOGGER.debug(f"Removed credentials for account {account_id}")
    
    async def async_get_authenticated_session(
        self, 
        username: str, 
        password: str,
        account_id: Optional[str] = None
    ) -> ClientSession:
        """Get authenticated session, refresh if needed."""
        # Check if we have a valid cached session
        if account_id and account_id in self._sessions:
            session_data = self._sessions[account_id]
            if self._is_session_valid(session_data):
                _LOGGER.debug(f"Using cached session for {account_id}")
                return session_data["session"]
        
        # Create new authenticated session
        session = await self._create_authenticated_session(username, password)
        
        # Cache the session
        if account_id:
            self._sessions[account_id] = {
                "session": session,
                "created_at": datetime.now(),
                "username": username,
            }
            # Save session metadata (not the actual session)
            await self._save_session_metadata()
        
        return session
    
    async def _create_authenticated_session(
        self, 
        username: str, 
        password: str
    ) -> ClientSession:
        """Create a new authenticated session."""
        _LOGGER.debug(f"Creating authenticated session for user {username} at {self.library_url}")
        
        # Create a new session with its own cookie jar for this account
        jar = CookieJar()
        # We need to create our own session here, not use the shared one
        import aiohttp
        connector = aiohttp.TCPConnector(ssl=True)
        session = aiohttp.ClientSession(
            cookie_jar=jar,
            connector=connector
        )
        
        try:
            # Get login page for CSRF token
            login_url = f"{self.library_url}/reader/"
            _LOGGER.debug(f"Fetching login page from {login_url}")
            async with session.get(login_url) as resp:
                if resp.status != 200:
                    _LOGGER.error(f"Failed to reach login page: {resp.status}")
                    raise ConfigEntryAuthFailed(f"Failed to reach login page: {resp.status}")
                    
                text = await resp.text()
                _LOGGER.debug(f"Login page fetched, length: {len(text)} characters")
                soup = BeautifulSoup(text, 'html.parser')
                
            # Extract CSRF token
            csrf_token = None
            csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
            if csrf_input:
                csrf_token = csrf_input.get('value')
                
            if not csrf_token:
                # Try meta tag
                csrf_meta = soup.find('meta', {'name': 'csrf-token'})
                if csrf_meta:
                    csrf_token = csrf_meta.get('content')
                    
            if not csrf_token:
                _LOGGER.error("Could not find CSRF token in login page")
                _LOGGER.debug(f"Page content preview: {text[:500]}...")
                raise ConfigEntryAuthFailed("Could not find CSRF token")
                
            # Prepare login data
            login_data = {
                'csrfmiddlewaretoken': csrf_token,
                'action': 'login',
                'username': username,
                'password': password,
                'rememberLogin': '1',  # Remember login for longer session
            }
            
            # Perform login - Post to the same URL as the form
            login_post_url = f"{self.library_url}/reader/"
            _LOGGER.debug(f"Posting login to {login_post_url} with username {username}")
            _LOGGER.debug(f"CSRF token: {csrf_token[:10]}...")
            
            # Add headers to mimic browser - match the original API
            headers = {
                'Referer': login_url,
                'Origin': 'https://www.bibkat.de',
            }
            
            async with session.post(
                login_post_url, 
                data=login_data,
                headers=headers,
                allow_redirects=True
            ) as resp:
                _LOGGER.debug(f"Login response status: {resp.status}")
                if resp.status != 200:
                    _LOGGER.error(f"Login failed with status {resp.status}")
                    text = await resp.text()
                    _LOGGER.debug(f"Error response: {text[:500]}...")
                    raise ConfigEntryAuthFailed(f"Login failed with status {resp.status}")
                    
                # Check if login was successful
                text = await resp.text()
                _LOGGER.debug(f"Login response length: {len(text)} characters")
                
                # Check for successful login indicators
                if "logout" in text.lower() or "abmelden" in text.lower() or "reader-view" in text:
                    _LOGGER.debug("Found logout link or reader-view - login successful")
                    found_indicator = True
                else:
                    _LOGGER.debug("No logout link found, checking other indicators")
                    # Additional checks for successful login
                    soup = BeautifulSoup(text, 'html.parser')
                    
                    # Check if we're on the account page
                    if soup.find('div', class_='reader-account') or soup.find('div', class_='account-info'):
                        _LOGGER.debug("Found account page elements - login successful")
                        found_indicator = True
                    # Check for reader content
                    elif soup.find('div', class_='reader-content') or soup.find('div', class_='reader-listing'):
                        _LOGGER.debug("Found reader content - login successful")
                        found_indicator = True
                    else:
                        found_indicator = False
                
                if not found_indicator:
                    _LOGGER.debug("No success indicators found, checking for errors")
                    # Check for error messages
                    error = soup.find('div', class_=['alert-danger', 'error-message', 'login-error'])
                    if not error:
                        # Look for any alert
                        error = soup.find('div', class_='alert')
                    
                    error_msg = error.get_text(strip=True) if error else None
                    
                    # If no error message found, provide more context
                    if not error_msg:
                        # Check if still on login page
                        if soup.find('form', {'action': '/reader/'}) or soup.find('input', {'name': 'username'}):
                            error_msg = "Still on login page - credentials may be incorrect"
                        else:
                            error_msg = "Login response unclear - no success indicators found"
                            # Log page title for debugging
                            title = soup.find('title')
                            if title:
                                _LOGGER.debug(f"Page title: {title.get_text()}")
                    
                    _LOGGER.error(f"Login failed: {error_msg}")
                    _LOGGER.debug(f"Response preview: {text[:1000]}...")
                    raise ConfigEntryAuthFailed(f"Login failed: {error_msg}")
                    
            _LOGGER.info(f"Successfully authenticated as {username}")
            return session
            
        except ConfigEntryAuthFailed:
            await session.close()
            raise
        except Exception as e:
            _LOGGER.error(f"Authentication error: {e}", exc_info=True)
            await session.close()
            raise ConfigEntryAuthFailed(f"Authentication failed: {str(e)}")
    
    def _is_session_valid(self, session_data: Dict[str, Any]) -> bool:
        """Check if a cached session is still valid."""
        if not session_data:
            return False
            
        created_at = session_data.get("created_at")
        if not created_at:
            return False
            
        # Check if session has expired
        age = datetime.now() - created_at
        if age > SESSION_TIMEOUT:
            _LOGGER.debug("Session expired due to timeout")
            return False
            
        # Session still valid
        return True
    
    async def _save_session_metadata(self) -> None:
        """Save session metadata (not actual sessions)."""
        metadata = {}
        for account_id, session_data in self._sessions.items():
            metadata[account_id] = {
                "created_at": session_data["created_at"].isoformat(),
                "username": session_data["username"],
            }
        await self._session_store.async_save(metadata)
    
    async def async_load_session_metadata(self) -> None:
        """Load session metadata on startup."""
        metadata = await self._session_store.async_load() or {}
        # Note: We don't restore actual sessions, just metadata
        # Sessions will be recreated on demand
        _LOGGER.debug(f"Loaded session metadata for {len(metadata)} accounts")
    
    async def async_validate_session(self, session: ClientSession) -> bool:
        """Validate if a session is still authenticated."""
        try:
            # Try to access account page
            async with session.get(f"{self.library_url}/reader/account/") as resp:
                if resp.status != 200:
                    return False
                    
                text = await resp.text()
                # Check for logout link as indicator of active session
                return "logout" in text.lower() or "abmelden" in text.lower()
                
        except Exception as e:
            _LOGGER.debug(f"Session validation failed: {e}")
            return False
    
    async def async_invalidate_session(self, account_id: str) -> None:
        """Invalidate a cached session."""
        if account_id in self._sessions:
            # Close the session
            session_data = self._sessions.pop(account_id)
            if session_data.get("session"):
                await session_data["session"].close()
            
            # Update metadata
            await self._save_session_metadata()
            _LOGGER.debug(f"Invalidated session for {account_id}")
    
    async def async_cleanup(self) -> None:
        """Clean up all sessions."""
        # Close all active sessions
        for account_id in list(self._sessions.keys()):
            await self.async_invalidate_session(account_id)
        
        _LOGGER.debug("Cleaned up all BibKat sessions")