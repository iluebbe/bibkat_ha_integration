"""API client for BibKat library system."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple
import re

import aiohttp
from bs4 import BeautifulSoup, Tag

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

try:
    from .const import BASE_URL, FAMILY_URL, LOGIN_URL
except ImportError:
    # For standalone testing
    BASE_URL = "https://www.bibkat.de/boehl/"
    LOGIN_URL = f"{BASE_URL}reader/"
    FAMILY_URL = f"{BASE_URL}reader/family/"

from .api_reservations import ReservationsMixin

_LOGGER: logging.Logger = logging.getLogger(__name__)


class BibKatAPI(ReservationsMixin):
    """BibKat API client."""

    def __init__(self, hass: HomeAssistant, username: str, password: str, base_url: str, account_id: str, renewal_rules_manager = None, use_browser: bool = False) -> None:
        """Initialize the API client."""
        self.hass = hass
        self._username: str = username
        self._password: str = password
        self._account_id: str = account_id
        self.csrf_token: Optional[str] = None
        self.logged_in: bool = False  # Keep for backward compatibility
        self._logged_in: bool = False
        self.use_browser: bool = use_browser
        self._browser_service = None
        self.renewal_rules_manager = renewal_rules_manager
        
        # Initialize auth helper
        from .auth_helper import BibKatAuthHelper
        self._auth_helper = BibKatAuthHelper(hass, base_url)
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Set URLs
        self.base_url: str = base_url.rstrip('/') + '/'
        self.login_url: str = f"{self.base_url}reader/"
        self.family_url: str = f"{self.base_url}reader/family/"

    async def _ensure_logged_in(self) -> bool:
        """Ensure we are logged in."""
        if self._logged_in and self._session:
            # Validate existing session
            if await self._auth_helper.async_validate_session(self._session):
                return True
            else:
                _LOGGER.info("Session expired, re-authenticating")
                self._logged_in = False

        return await self._login()
    
    async def _login(self) -> bool:
        """Log in to the library website."""
        try:
            # Get authenticated session from auth helper
            self._session = await self._auth_helper.async_get_authenticated_session(
                self._username,
                self._password,
                self._account_id
            )
            self._logged_in = True
            self.logged_in = True  # Keep backward compatibility
            
            # Extract CSRF token from session for operations that need it
            async with self._session.get(self.login_url) as response:
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')
                csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
                if csrf_input:
                    self.csrf_token = csrf_input.get('value', '')
            
            return True
            
        except ConfigEntryAuthFailed as e:
            _LOGGER.error(f"Authentication failed: {e}")
            return False
        except Exception as e:
            _LOGGER.error(f"Unexpected error during login: {e}")
            return False

    async def get_borrowed_media(self) -> List[Dict[str, Any]]:
        """Get all borrowed media from main and family accounts."""
        if not await self._ensure_logged_in():
            _LOGGER.error("Not logged in")
            return []

        _LOGGER.debug(f"Fetching borrowed media for {self.base_url}")
        all_media: List[Dict[str, Any]] = []
        media_by_id: Dict[str, Dict[str, Any]] = {}

        # Get media from main account
        try:
            _LOGGER.debug(f"Fetching main account media from: {self.login_url}")
            main_media: List[Dict[str, Any]] = await self._get_media_from_page(self.login_url, "main")
            _LOGGER.debug(f"Found {len(main_media)} media items on main account page")
            for media in main_media:
                media_id = media.get('media_id')
                if media_id:
                    media['found_on'] = ["main"]  # Track where it was found
                    media_by_id[media_id] = media
                    all_media.append(media)
                    _LOGGER.debug(f"Added media from main: {media.get('title', 'Unknown')} (ID: {media_id})")
        except Exception as e:
            _LOGGER.error("Error fetching main account media: %s", e)

        # Add random delay before accessing family page (0.3-1.5 seconds)
        await asyncio.sleep(random.uniform(0.3, 1.5))
        
        # Get media from family accounts
        try:
            _LOGGER.debug(f"Fetching family account media from: {self.family_url}")
            family_media: List[Dict[str, Any]] = await self._get_media_from_page(self.family_url, "family")
            _LOGGER.debug(f"Found {len(family_media)} media items on family page")
            for media in family_media:
                media_id = media.get('media_id')
                if media_id:
                    if media_id in media_by_id:
                        # Already seen - just add family to found_on list
                        media_by_id[media_id]['found_on'].append("family")
                        _LOGGER.debug(f"Media found on multiple pages: {media.get('title')} (ID: {media_id})")
                    else:
                        # New media - add it
                        media['found_on'] = ["family"]
                        media_by_id[media_id] = media
                        all_media.append(media)
                        _LOGGER.debug(f"Added media from family: {media.get('title', 'Unknown')} (ID: {media_id})")
        except Exception as e:
            _LOGGER.error("Error fetching family account media: %s", e)

        # Fetch additional details with randomized rate limiting
        # Determine if we should fetch all details (once per day) or just urgent ones
        should_fetch_all_details = False
        
        # Import the detail fetch interval
        try:
            from .const import DETAIL_FETCH_INTERVAL
        except ImportError:
            DETAIL_FETCH_INTERVAL = timedelta(hours=24)
        
        # Check if we should do a full detail fetch (stored in instance variable)
        if not hasattr(self, '_last_full_detail_fetch'):
            self._last_full_detail_fetch = None
        
        # Check if enough time has passed for a full detail fetch
        if self._last_full_detail_fetch is None or (datetime.now() - self._last_full_detail_fetch) >= DETAIL_FETCH_INTERVAL:
            should_fetch_all_details = True
            self._last_full_detail_fetch = datetime.now()
            _LOGGER.debug("Performing scheduled detail fetch for all renewable items (every %s)", DETAIL_FETCH_INTERVAL)
        
        # Fetch details for renewable items
        items_to_fetch_details = []
        for media in all_media:
            if media.get('renewable') and media.get('detail_url'):
                # Only fetch details during the scheduled daily fetch
                if should_fetch_all_details:
                    items_to_fetch_details.append(media)
        
        if items_to_fetch_details:
            _LOGGER.debug(f"Fetching details for {len(items_to_fetch_details)} renewable items")
            
            for i, media in enumerate(items_to_fetch_details):
                try:
                    # Add a randomized delay to avoid rate limiting (act like a human)
                    # First request has shorter delay, subsequent ones are longer
                    if i == 0:
                        delay = random.uniform(0.3, 0.8)
                    else:
                        delay = random.uniform(0.5, 1.5)
                    
                    await asyncio.sleep(delay)
                    _LOGGER.debug(f"Fetching details for '{media.get('title', 'Unknown')}' (days remaining: {media.get('days_remaining', 999)})")
                    details: Dict[str, Any] = await self._fetch_media_details(media['detail_url'])
                    media.update(details)
                    
                    # Log if we found renewal date
                    if details.get('renewal_date_iso'):
                        _LOGGER.debug(f"Found renewal date for '{media.get('title', 'Unknown')}': {details.get('renewal_date', 'Unknown')}")
                except Exception as e:
                    _LOGGER.error(f"Error fetching details for {media['title']}: {e}")

        _LOGGER.debug(f"Total media found: {len(all_media)} items")
        
        # Summarize by account
        by_account = {}
        for media in all_media:
            owner = media.get('owner_number', 'main')
            if owner not in by_account:
                by_account[owner] = []
            by_account[owner].append(media)
        
        _LOGGER.debug("Media summary by account:")
        for owner, items in by_account.items():
            _LOGGER.debug(f"  Account {owner}: {len(items)} items")
            for media in items:
                _LOGGER.debug(
                    f"    - {media.get('title', 'Unknown')} "
                    f"(ID: {media.get('media_id', 'None')}, Found on: {media.get('found_on', [])})"
                )
        
        # Store for renewal date calculation fallback
        self._last_media_list = all_media
        
        return all_media
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information including balance."""
        if not self.logged_in:
            _LOGGER.error("Not logged in")
            return {}
        
        account_info: Dict[str, Any] = {
            "balance": 0.0,
            "currency": "EUR",
            "card_expiry": None,
            "reservations": 0,
        }
        
        try:
            async with self._session.get(self.login_url) as response:
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')
                
                # Look for balance information
                # Pattern: "0,00 € Kontostand"
                balance_text = soup.find(text=lambda t: t and 'Kontostand' in t)
                if balance_text:
                    # Extract the amount
                    import re
                    balance_match = re.search(r'(\d+,\d+)\s*€', str(balance_text))
                    if balance_match:
                        # Convert German decimal format to float
                        balance_str = balance_match.group(1).replace(',', '.')
                        account_info["balance"] = float(balance_str)
                
                # Look for card expiry
                # Pattern: "Karte gültig bis: 31.12.2025"
                expiry_text = soup.find(text=lambda t: t and 'Karte gültig bis' in t)
                if expiry_text:
                    expiry_match = re.search(r'bis:\s*(\d{1,2}\.\d{1,2}\.\d{4})', str(expiry_text))
                    if expiry_match:
                        expiry_date_str = expiry_match.group(1)
                        parsed_date = self.parse_german_date(expiry_date_str)
                        if parsed_date:
                            account_info["card_expiry"] = parsed_date.isoformat()
                
                # Look for reservations count
                reservations_elem = soup.find('a', href=lambda h: h and 'reservations' in h)
                if reservations_elem:
                    # Extract count from text like "Vormerkungen (2)"
                    res_text = reservations_elem.text
                    res_match = re.search(r'\((\d+)\)', res_text)
                    if res_match:
                        account_info["reservations"] = int(res_match.group(1))
                
                _LOGGER.debug(f"Account info: {account_info}")
                
        except Exception as e:
            _LOGGER.error(f"Error fetching account info: {e}")
        
        return account_info

    async def _get_media_from_page(self, url: str, account_type: str) -> List[Dict[str, Any]]:
        """Extract media information from a page."""
        media_list: List[Dict[str, Any]] = []

        _LOGGER.debug(f"Fetching media from URL: {url}")
        async with self._session.get(url) as response:
            if response.status != 200:
                _LOGGER.error(f"Failed to fetch {url}: Status {response.status}")
                return media_list
                
            text: str = await response.text()
            # Store the page content for catalog code extraction
            self._last_page_content = text
            soup: BeautifulSoup = BeautifulSoup(text, 'html.parser')
            
            # For family page, try to extract current account context
            current_account_number = None
            if account_type == "family":
                # Look for account headers like "Konto Nr. 689"
                account_headers = soup.find_all('h4', class_='reader-content-title')
                _LOGGER.debug(f"Found {len(account_headers)} account headers on family page")

            # Update CSRF token if present
            csrf_input: Optional[Tag] = soup.find('input', {'name': 'csrfmiddlewaretoken'})
            if csrf_input:
                self.csrf_token = csrf_input.get('value', '')

            # For family page, process by account sections
            if account_type == "family":
                # Process borrowed media
                listing = soup.find('div', class_='reader-listing-lendings')
                if listing:
                    _LOGGER.info("Found family listing section")
                    
                    # Get all items in the listing
                    all_items = listing.find_all('div', class_='item')
                    _LOGGER.info(f"Found {len(all_items)} total items on family page")
                    
                    # Find all account headers
                    headers = listing.find_all('h4', class_='reader-content-title')
                    _LOGGER.info(f"Found {len(headers)} account headers on family page")
                    
                    # Process by finding which header each item belongs to
                    current_account_number = None
                    items_processed = 0
                    items_added = 0
                    # Get all direct children, including text nodes
                    for element in listing.find_all(['h4', 'div']):
                        if element.name == 'h4' and 'reader-content-title' in element.get('class', []):
                            # This is a header
                            header_text = element.get_text()
                            _LOGGER.debug(f"Processing header: {header_text}")
                            match = re.search(r'Konto\s+Nr\.\s*(\d+)', header_text)
                            if match:
                                current_account_number = match.group(1)
                                _LOGGER.info(f"Now processing items for account: {current_account_number}")
                        elif element.name == 'div' and 'item' in element.get('class', []):
                            # This is an item
                            if current_account_number and 'item-variant-message' not in element.get('class', []):
                                items_processed += 1
                                _LOGGER.debug(f"Found item div with ID: {element.get('id', 'NO_ID')} for account {current_account_number}")
                                media_info = self._extract_media_info(element)
                                if media_info:
                                    # Only add if it's actually borrowed (has a due date)
                                    if media_info.get('due_date'):
                                        media_info['account'] = account_type
                                        media_info['owner_name'] = f'Leser {current_account_number}'
                                        media_info['owner_number'] = current_account_number
                                        media_list.append(media_info)
                                        items_added += 1
                                        _LOGGER.info(f"Found borrowed media: '{media_info.get('title', 'Unknown')}' (ID: {media_info.get('media_id', 'NO_ID')}) for account {current_account_number}")
                                    else:
                                        _LOGGER.debug(f"Skipping reserved/non-borrowed item: '{media_info.get('title', 'Unknown')}'")
                                else:
                                    _LOGGER.warning("Failed to extract media info from item")
                    
                    _LOGGER.info(f"Family page summary: Processed {items_processed} items, added {items_added} borrowed media")
                else:
                    _LOGGER.warning("No reader-listing-lendings div found on family page")
            else:
                # For main account page, use the standard approach
                items: List[Tag] = soup.find_all('div', class_='item')
                _LOGGER.debug(f"Found {len(items)} item divs on {account_type} page")
                
                for item in items:
                    # Skip message items
                    if 'item-variant-message' in item.get('class', []):
                        _LOGGER.debug("Skipping message item")
                        continue

                    media_info: Optional[Dict[str, Any]] = self._extract_media_info(item)
                    if media_info:
                        # Only add if it's actually borrowed (has a due date)
                        if media_info.get('due_date'):
                            media_info['account'] = account_type
                            media_list.append(media_info)
                            _LOGGER.debug(f"Extracted borrowed media: {media_info.get('title', 'Unknown')} (ID: {media_info.get('media_id', 'Unknown')})")
                        else:
                            _LOGGER.info(f"Found reserved/non-borrowed item on main page: '{media_info.get('title', 'Unknown')}' - should be handled by reservation system")

        _LOGGER.info("Found %d media items on %s page", len(media_list), account_type)
        return media_list

    def _extract_owner_from_item(self, item: Tag) -> Optional[Dict[str, str]]:
        """Extract owner information from a family page item."""
        try:
            # Look for reader info in the item
            # This could be in a div with class like 'item-reader' or similar
            reader_elem = item.find('div', class_='item-reader')
            if reader_elem:
                reader_text = reader_elem.text.strip()
                # Try to extract reader number (e.g., "Leser 689")
                import re
                match = re.search(r'(\d+)', reader_text)
                if match:
                    return {
                        'name': reader_text,
                        'number': match.group(1)
                    }
            
            # Alternative: Look for any text that might indicate the reader
            # Support both German "Leser" and potential English "Reader"
            all_text = item.get_text()
            match = re.search(r'(?:Leser|Reader)\s*(\d+)', all_text, re.IGNORECASE)
            if match:
                # Extract the actual prefix used in the text
                prefix = all_text[match.start():match.start()+5].strip()
                return {
                    'name': f'{prefix} {match.group(1)}',
                    'number': match.group(1)
                }
                    
        except Exception as e:
            _LOGGER.debug(f"Error extracting owner info: {e}")
            
        return None
    
    def _extract_media_info(self, item: Tag) -> Optional[Dict[str, Any]]:
        """Extract media information from an item element."""
        try:
            # Debug logging commented to reduce verbosity
            # _LOGGER.debug(f"Extracting media info from item: {item.get('id', 'NO_ID')}")
            # _LOGGER.debug(f"Item attributes: {item.attrs}")
            
            # Extract media ID - might be in different attributes
            media_id = item.get('id', '')
            if media_id and media_id.startswith('media-'):
                # Extract just the numeric part
                media_id = media_id.replace('media-', '')
                pass  # _LOGGER.debug(f"Found media ID from id attribute: {media_id}")
            
            if not media_id:
                # Try data-id attribute (more common)
                media_id = item.get('data-id', '')
                if media_id:
                    pass  # _LOGGER.debug(f"Found media ID from data-id attribute: {media_id}")
            
            if not media_id:
                # Try data-media-id attribute
                media_id = item.get('data-media-id', '')
                if media_id:
                    pass  # _LOGGER.debug(f"Found media ID from data-media-id attribute: {media_id}")
            
            if not media_id:
                # Try to find it in a data attribute
                for attr, value in item.attrs.items():
                    if 'data-id' in attr:
                        media_id = value
                        pass  # _LOGGER.debug(f"Found media ID from {attr} attribute: {media_id}")
                        break
            
            if not media_id:
                _LOGGER.warning("No media ID found for item - will generate one later")
                # Generate a unique ID based on title later
            
            media_info: Dict[str, Any] = {
                'media_id': media_id,
                'title': '',
                'author': '',
                'due_date': '',
                'due_date_iso': None,
                'renewable': False,
                'days_remaining': 0,
                'detail_url': None,
                'renewal_date': '',
                'renewal_date_iso': None,
                'is_renewable_now': False,
            }

            # Extract title and detail URL
            title_elem = item.find('div', class_='item-title')
            if title_elem:
                media_info['title'] = title_elem.text.strip()
                # Find the link to the detail page
                title_link = title_elem.find('a')
                if title_link and title_link.get('href'):
                    media_info['detail_url'] = self.base_url.rstrip('/') + title_link.get('href')
            else:
                # Try alternative: title might be directly in a link
                title_link = item.find('a', class_='item-link')
                if title_link:
                    media_info['title'] = title_link.text.strip()
                    if title_link.get('href'):
                        media_info['detail_url'] = self.base_url.rstrip('/') + title_link.get('href')
                else:
                    # Log what we found to debug
                    _LOGGER.warning(f"No title found in item. Item HTML: {str(item)[:200]}...")
                    return None  # No title, not a valid media item

            # Extract author
            author_elem = item.find('div', class_='item-author')
            if author_elem:
                media_info['author'] = author_elem.text.strip()

            # Extract due date
            status_elem = item.find('div', class_='item-account-status')
            if status_elem:
                due_text = status_elem.get('title', status_elem.text)
                media_info['due_date'] = due_text.strip()
                
                # Calculate days remaining and get ISO date
                days_remaining, iso_date = self._calculate_days_remaining(due_text)
                media_info['days_remaining'] = days_remaining
                media_info['due_date_iso'] = iso_date

            # Check renewal date from rules if available
            if self.renewal_rules_manager and media_info['due_date_iso']:
                try:
                    due_date = date.fromisoformat(media_info['due_date_iso'])
                    renewal_date = self.renewal_rules_manager.calculate_renewal_date(self.base_url, due_date)
                    if renewal_date:
                        media_info['renewal_date'] = renewal_date.strftime('%d.%m.%Y')
                        media_info['renewal_date_iso'] = renewal_date.isoformat()
                        # Check if renewable now
                        media_info['is_renewable_now'] = date.today() >= renewal_date
                        _LOGGER.debug(f"Calculated renewal date from rules: {renewal_date} for due date {due_date}")
                except Exception as e:
                    _LOGGER.debug(f"Error calculating renewal date from rules: {e}")
            
            # Check if renewable
            actions = item.find('div', class_='item-actions')
            if actions:
                renew_action = actions.find(attrs={'data-action': 'renew'})
                if renew_action:
                    media_info['renewable'] = True
                    # Try to extract media ID from the renew action if we don't have it yet
                    if not media_info['media_id']:
                        # Look for data-media-id attribute
                        if renew_action.get('data-media-id'):
                            media_info['media_id'] = renew_action.get('data-media-id')
                        # Or try to extract from onclick or other attributes
                        elif renew_action.get('onclick'):
                            onclick = renew_action.get('onclick')
                            # Look for patterns like renewMedia('12345')
                            match = re.search(r"['\"](\d+)['\"]", onclick)
                            if match:
                                media_info['media_id'] = match.group(1)
                    
                    # Mark as renewable now if we found the action
                    # (the new interface only shows the button when renewable)
                    media_info['is_renewable_now'] = True

            # If still no media_id, generate one from title and author
            if not media_info['media_id'] and media_info['title']:
                import hashlib
                unique_string = f"{media_info['title']}_{media_info['author']}_{media_info['due_date']}"
                media_info['media_id'] = f"gen_{hashlib.md5(unique_string.encode()).hexdigest()[:8]}"
                _LOGGER.debug(f"Generated media ID {media_info['media_id']} for {media_info['title']}")

            _LOGGER.info(
                f"Successfully extracted media: ID={media_info['media_id']}, "
                f"Title='{media_info['title']}', Renewable={media_info['renewable']}"
            )
            return media_info

        except Exception as e:
            _LOGGER.error("Error extracting media info: %s", e)
            return None

    def parse_german_date(self, date_text: str) -> Optional[date]:
        """Parse German date formats to date object."""
        # German month names
        months: Dict[str, int] = {
            'Januar': 1, 'Februar': 2, 'März': 3, 'April': 4,
            'Mai': 5, 'Juni': 6, 'Juli': 7, 'August': 8,
            'September': 9, 'Oktober': 10, 'November': 11, 'Dezember': 12
        }
        
        # Short month names
        short_months: Dict[str, int] = {
            'Jan.': 1, 'Feb.': 2, 'Mär.': 3, 'Apr.': 4,
            'Mai': 5, 'Jun.': 6, 'Jul.': 7, 'Aug.': 8,
            'Sep.': 9, 'Okt.': 10, 'Nov.': 11, 'Dez.': 12
        }
        
        try:
            # Try format: "So., 13. Jul." or "Sonntag, 13. Juli"
            date_match: Optional[re.Match[str]] = re.search(r'(\d+)\.\s*(\w+\.?)', date_text)
            if date_match:
                day: int = int(date_match.group(1))
                month_str: str = date_match.group(2)
                
                # Check both full and short month names
                month: Optional[int] = months.get(month_str) or short_months.get(month_str)
                
                if month:
                    # Determine year
                    current_year: int = datetime.now().year
                    current_month: int = datetime.now().month
                    
                    # Start with current year
                    parsed_date: date = date(current_year, month, day)
                    
                    today: date = date.today()
                    
                    # If the date is in the past but within 2 months, keep current year
                    # (for recently overdue items)
                    if parsed_date < today:
                        days_past: int = (today - parsed_date).days
                        if days_past > 60:  # More than 2 months in the past
                            # Assume it's for next year
                            parsed_date = date(current_year + 1, month, day)
                    
                    return parsed_date
                    
            # Try format: "06.07.2025" or "6. Juli 2025"
            full_date_match: Optional[re.Match[str]] = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', date_text)
            if full_date_match:
                day = int(full_date_match.group(1))
                month = int(full_date_match.group(2))
                year = int(full_date_match.group(3))
                return date(year, month, day)
                
        except Exception as e:
            _LOGGER.error(f"Error parsing date '{date_text}': {e}")
            
        return None

    def _calculate_days_remaining(self, due_text: str) -> Tuple[int, Optional[str]]:
        """Calculate days remaining until due date and return ISO date."""
        try:
            # Extract date from text like "Rückgabe bis: Sonntag, 13. Juli"
            if 'bis:' in due_text:
                date_part: str = due_text.split('bis:')[-1].strip()
            else:
                date_part = due_text.strip()
                
            parsed_date: Optional[date] = self.parse_german_date(date_part)
            
            if parsed_date:
                days_diff: int = (parsed_date - date.today()).days
                iso_date: str = parsed_date.isoformat()
                return max(0, days_diff), iso_date
            else:
                _LOGGER.debug(f"Could not parse date from: {date_part}")
                
        except Exception as e:
            _LOGGER.error(f"Error calculating days remaining: {e}")
            
        return 0, None

    async def _fetch_media_details(self, detail_url: str) -> Dict[str, Any]:
        """Fetch additional details from media detail page."""
        details: Dict[str, Any] = {
            'renewal_date': '',
            'renewal_date_iso': None,
            'is_renewable_now': False,
        }
        
        try:
            async with self._session.get(detail_url) as response:
                if response.status != 200:
                    return details
                    
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')
                
                # Look for renewal date information
                # Pattern: "Das Medium kann ab dem 6. Juli online verlängert werden."
                renewal_text = soup.find(text=lambda t: t and 'kann ab dem' in t and 'online verlängert werden' in t)
                if renewal_text:
                    # Extract the date part
                    date_match = re.search(r'ab dem (\d+\.\s*\w+\.?(?:\s*\d{4})?)', renewal_text)
                    if date_match:
                        renewal_date_text = date_match.group(1)
                        details['renewal_date'] = renewal_date_text
                        
                        # Parse to ISO date
                        parsed_date = self.parse_german_date(renewal_date_text)
                        if parsed_date:
                            details['renewal_date_iso'] = parsed_date.isoformat()
                            # Check if renewable now
                            details['is_renewable_now'] = date.today() >= parsed_date
                    else:
                        details['renewal_date'] = renewal_text.strip()
                
                _LOGGER.debug(f"Fetched details for {detail_url}: {details}")
                
        except Exception as e:
            _LOGGER.error(f"Error fetching media details from {detail_url}: {e}")
            
        return details

    async def _learn_renewal_rules(self, media_id: str, renewal_date_iso: str) -> None:
        """Learn renewal rules from a successful browser extraction."""
        try:
            # Find the media in our current data to get due date
            all_media = await self.get_borrowed_media()
            for media in all_media:
                if media.get('media_id') == media_id and media.get('due_date_iso'):
                    due_date = date.fromisoformat(media['due_date_iso'])
                    renewal_date = date.fromisoformat(renewal_date_iso)
                    
                    # Calculate offset
                    offset_days = (due_date - renewal_date).days
                    
                    # Update rules
                    self.renewal_rules_manager.update_rules(self.base_url, offset_days)
                    _LOGGER.info(
                        f"Learned renewal rule for {self.base_url}: "
                        f"Can renew {offset_days} days before due date"
                    )
                    break
        except Exception as e:
            _LOGGER.error(f"Error learning renewal rules: {e}")
    
    async def renew_all_media(self) -> Dict[str, Any]:
        """Renew all renewable media."""
        if not self.logged_in:
            return {'success': False, 'message': 'Not logged in'}

        result: Dict[str, Any] = {
            'success': True,
            'renewed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
            'messages': []
        }

        # Get all media
        media_list: List[Dict[str, Any]] = await self.get_borrowed_media()
        
        # Filter media that are marked as renewable (not necessarily renewable NOW)
        renewable_media: List[Dict[str, Any]] = [m for m in media_list if m.get('renewable', False)]
        
        if not renewable_media:
            return {'success': True, 'message': 'Keine verlängerbaren Medien gefunden'}

        # Process each media using the unified renew_media method
        for media in renewable_media:
            try:
                media_id = media.get('media_id')
                title = media.get('title', 'Unknown')
                
                # Use the public renew_media method which handles both cases
                renew_result: Dict[str, Any] = await self.renew_media(media_id)
                
                if renew_result.get('success'):
                    # Successfully renewed
                    result['renewed'] += 1
                    result['messages'].append(f"{title}: Erfolgreich verlängert")
                elif renew_result.get('renewal_date'):
                    # Not renewable yet, but we got the date
                    result['skipped'] += 1
                    result['messages'].append(f"{title}: Verlängerbar ab {renew_result['renewal_date']}")
                else:
                    # Failed to renew
                    result['failed'] += 1
                    error_msg = renew_result.get('message', 'Unbekannter Fehler')
                    result['errors'].append(f"{title}: {error_msg}")
                    
            except Exception as e:
                result['failed'] += 1
                result['errors'].append(f"{media.get('title', 'Unknown')}: Fehler - {str(e)}")
                _LOGGER.error(f"Error processing {media.get('media_id')}: {e}")
        
        # Build summary message
        parts = []
        if result['renewed'] > 0:
            parts.append(f"{result['renewed']} verlängert")
        if result['skipped'] > 0:
            parts.append(f"{result['skipped']} noch nicht verlängerbar")
        if result['failed'] > 0:
            parts.append(f"{result['failed']} fehlgeschlagen")
            
        if parts:
            result['message'] = "Ergebnis: " + ", ".join(parts)
        else:
            result['message'] = "Keine Medien verarbeitet"
        
        return result

    async def renew_media(self, media_id: str) -> Dict[str, Any]:
        """Renew a single media item or extract renewal date - public method."""
        # First, check if the media is renewable now
        media_info = None
        for media in getattr(self, '_last_media_list', []):
            if media.get('media_id') == media_id:
                media_info = media
                break
        
        if not media_info:
            _LOGGER.warning(f"Media {media_id} not found in last media list")
            return {'success': False, 'message': 'Medium nicht gefunden'}
        
        # If the media is renewable now, try to renew it
        if media_info.get('is_renewable_now', False):
            _LOGGER.debug(f"Media {media_id} is renewable now, attempting renewal")
            return await self._renew_single_media(media_id)
        else:
            _LOGGER.debug(f"Media {media_id} is not renewable yet, extracting renewal date")
            # Try to extract the renewal date
            date_result = await self._extract_renewal_date(media_id)
            
            # Make sure date_result is not None
            if date_result is None:
                date_result = {
                    'success': False,
                    'message': 'Fehler bei der Datumsextraktion'
                }
            
            # Convert the result to match expected format
            if date_result.get('success'):
                return {
                    'success': False,  # Renewal wasn't successful, but we got the date
                    'message': f'Medium kann erst ab dem {date_result.get("renewal_date")} verlängert werden',
                    'renewal_date': date_result.get('renewal_date'),
                    'renewal_date_iso': date_result.get('renewal_date_iso'),
                    'source': date_result.get('source', 'unknown')
                }
            else:
                return {
                    'success': False,
                    'message': date_result.get('message', 'Verlängerungsdatum konnte nicht ermittelt werden')
                }
    
    async def fetch_media_details(self, detail_url: str) -> Dict[str, Any]:
        """Fetch media details from detail page - public method."""
        return await self._fetch_media_details(detail_url)
        
    async def _renew_single_media(self, media_id: str) -> Dict[str, Any]:
        """Actually renew a single media item (when renewal is possible)."""
        clean_media_id = media_id.replace('media-', '')
        _LOGGER.debug(f"Attempting actual renewal for media ID: {clean_media_id}")

        # Step 1: Get the modal content with the renewal confirmation
        # The API might use a different base URL structure
        # First, let's log what we have
        _LOGGER.debug(f"Current base_url: {self.base_url}")
        _LOGGER.debug(f"Current family_url: {self.family_url}")
        
        # Try to extract the catalog code from the page if needed
        # The URL pattern seems to be /CATALOG_CODE/api/renew/
        api_url = f"{self.base_url}api/renew/"
        
        # Check if we need to get a catalog code first
        if not hasattr(self, '_catalog_code'):
            self._catalog_code = None
            # Try to find it from the current page content we already have
            if hasattr(self, '_last_page_content') and self._last_page_content:
                # Look for the catalog code in JavaScript onclick handlers
                # Pattern: BGX followed by 6 digits
                import re
                match = re.search(r'BGX\d{6}', self._last_page_content)
                if match:
                    self._catalog_code = match.group(0)
                    _LOGGER.info(f"Found catalog code from page content: {self._catalog_code}")
        
        # If we have a catalog code, use it in the URL
        if self._catalog_code:
            # The API URL pattern is: https://www.bibkat.de/{CATALOG_CODE}/api/renew/
            # We need to use the base domain, not the library-specific URL
            api_url = f"https://www.bibkat.de/{self._catalog_code}/api/renew/"
            _LOGGER.info(f"Using catalog-based API URL: {api_url}")
        else:
            # Fallback to standard API URL
            api_url = f"{self.base_url}api/renew/"
            _LOGGER.warning("No catalog code found, using fallback URL")
        
        _LOGGER.debug(f"Using API URL: {api_url}")
        
        params = {
            'payload': clean_media_id,
            '_': str(int(datetime.now().timestamp() * 1000))  # Timestamp
        }
        
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': self.family_url,
        }

        try:
            # Step 1: GET request to get the modal content
            _LOGGER.debug(f"Step 1: Getting renewal modal from {api_url} for media {clean_media_id}")
            _LOGGER.debug(f"Request params: {params}")
            _LOGGER.debug(f"Request headers: {headers}")
            
            async with self._session.get(api_url, params=params, headers=headers) as response:
                if response.status != 200:
                    response_text = await response.text()
                    _LOGGER.warning(f"Failed to get renewal modal: status {response.status}")
                    _LOGGER.warning(f"Response headers: {response.headers}")
                    _LOGGER.warning(f"Response text (first 500 chars): {response_text[:500] if response_text else 'No response text'}")
                    _LOGGER.warning(f"Full URL attempted: {response.url}")
                    return {'success': False, 'message': 'Fehler beim Abrufen des Verlängerungsdialogs'}
                
                data = await response.json()
                _LOGGER.debug(f"Modal response: {data}")
                
                if not data.get('meta', {}).get('success'):
                    return {'success': False, 'message': 'Verlängerung fehlgeschlagen'}
                
                # Check if we got the renewal action in the response
                actions = data.get('data', {}).get('actions', [])
                renew_action = None
                for action in actions:
                    if action.get('function') == 'renew' and action.get('method') == 'POST':
                        renew_action = action
                        break
                
                if not renew_action:
                    _LOGGER.warning("No renewal action found in modal response")
                    return {'success': False, 'message': 'Keine Verlängerungsaktion gefunden'}
                
            # Step 2: POST request to actually renew
            _LOGGER.debug(f"Step 2: Executing renewal POST for media {clean_media_id}")
            
            # The POST uses the same URL but with POST method
            post_data = {
                'payload': clean_media_id,
            }
            
            # Add CSRF token if available
            if self.csrf_token:
                headers['X-CSRFToken'] = self.csrf_token
                post_data['csrfmiddlewaretoken'] = self.csrf_token
            
            async with self._session.post(api_url, data=post_data, headers=headers) as response:
                if response.status == 200:
                    post_result = await response.json()
                    _LOGGER.debug(f"Renewal POST response: {post_result}")
                    
                    if post_result.get('meta', {}).get('success'):
                        return {
                            'success': True,
                            'message': 'Medium erfolgreich verlängert'
                        }
                    else:
                        return {
                            'success': False,
                            'message': post_result.get('data', {}).get('message', 'Verlängerung fehlgeschlagen')
                        }
                else:
                    _LOGGER.warning(f"Renewal POST failed with status {response.status}")
                    return {'success': False, 'message': f'Verlängerung fehlgeschlagen (Status {response.status})'}
                    
        except Exception as e:
            _LOGGER.error(f"Renewal failed for media {clean_media_id}: {e}")
            return {'success': False, 'message': f'Fehler bei der Verlängerung: {str(e)}'}

    async def _extract_renewal_date(self, media_id: str) -> Dict[str, Any]:
        """Extract the renewal date for a media item (when renewal is not yet possible)."""
        clean_media_id = media_id.replace('media-', '')
        _LOGGER.debug(f"Attempting to extract renewal date for media ID: {clean_media_id}")

        # Method 1: Browser extraction (if enabled) - PRIMARY METHOD
        if self.use_browser:
            _LOGGER.debug(f"Using browser to extract renewal date")
            try:
                from .browser_service import BrowserService
                if not self._browser_service:
                    self._browser_service = BrowserService(self.base_url)
                
                if await self._browser_service.is_available():
                    browser_result = await self._browser_service.extract_renewal_date(
                        self._username, self._password, clean_media_id
                    )
                    
                    if browser_result.get('success') and browser_result.get('renewal_date_iso'):
                        # Learn and save the rule
                        if 'renewal_offset_days' in browser_result:
                            self.renewal_rules_manager.update_rules(
                                self.base_url, 
                                browser_result['renewal_offset_days']
                            )
                            _LOGGER.info(f"Learned rule: {browser_result['renewal_offset_days']} days before due date")
                        
                        return {
                            'success': True,
                            'renewal_date': browser_result.get('renewal_date'),
                            'renewal_date_iso': browser_result.get('renewal_date_iso'),
                            'source': 'browser'
                        }
                else:
                    _LOGGER.warning("Browser mode enabled, but Playwright not installed")
            except Exception as e:
                _LOGGER.error(f"Browser extraction failed: {e}")

        # Method 2: Check if we already have rules and can calculate
        if self.renewal_rules_manager:
            for media in getattr(self, '_last_media_list', []):
                if media.get('media_id') == media_id and media.get('due_date_iso'):
                    due_date = date.fromisoformat(media['due_date_iso'])
                    renewal_date = self.renewal_rules_manager.calculate_renewal_date(self.base_url, due_date)
                    if renewal_date:
                        _LOGGER.debug(f"Calculated renewal date from rules: {renewal_date}")
                        return {
                            'success': True,
                            'renewal_date': renewal_date.strftime('%d.%m.%Y'),
                            'renewal_date_iso': renewal_date.isoformat(),
                            'source': 'rules'
                        }

        # Method 3: Fallback to default (6 days before due date)
        _LOGGER.debug(f"Using fallback: 6 days before due date")
        for media in getattr(self, '_last_media_list', []):
            if media.get('media_id') == media_id and media.get('due_date_iso'):
                due_date = date.fromisoformat(media['due_date_iso'])
                renewal_date = due_date - timedelta(days=6)
                return {
                    'success': True,
                    'renewal_date': renewal_date.strftime('%d.%m.%Y'),
                    'renewal_date_iso': renewal_date.isoformat(),
                    'source': 'fallback',
                    'note': 'Geschätztes Datum (6 Tage vor Fälligkeit)'
                }

        return {
            'success': False,
            'message': 'Verlängerungsdatum konnte nicht ermittelt werden',
            'note': 'Keine Regeln vorhanden und Browser-Extraktion nicht verfügbar'
        }
    
    async def _learn_renewal_rules(self, media_id: str, renewal_date_iso: str) -> None:
        """Learn renewal rules by comparing renewal date with due date."""
        try:
            # Find the media in our last list
            for media in getattr(self, '_last_media_list', []):
                if media.get('media_id') == media_id and media.get('due_date_iso'):
                    due_date = date.fromisoformat(media['due_date_iso'])
                    renewal_date = date.fromisoformat(renewal_date_iso)
                    
                    # Calculate offset in days
                    offset_days = (due_date - renewal_date).days
                    
                    _LOGGER.info(f"Learned renewal rule: {offset_days} days before due date")
                    
                    # Update rules
                    if self.renewal_rules_manager:
                        self.renewal_rules_manager.update_rules(self.base_url, offset_days)
                    
                    break
        except Exception as e:
            _LOGGER.error(f"Error learning renewal rules: {e}")