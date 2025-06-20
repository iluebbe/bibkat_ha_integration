"""API extension for BibKat reservations/holds."""
from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from bs4 import BeautifulSoup, Tag

_LOGGER = logging.getLogger(__name__)


class ReservationsMixin:
    """Mixin to add reservation functionality to BibKatAPI."""
    
    async def get_reserved_media(self) -> List[Dict[str, Any]]:
        """Get list of reserved/held media items from all accounts."""
        if not self.logged_in:
            _LOGGER.error("Not logged in")
            return []
        
        all_reservations: List[Dict[str, Any]] = []
        reservations_by_id: Dict[str, Dict[str, Any]] = {}
        
        # URLs to check for reservations
        urls_to_check = [
            (self.login_url, "main"),      # Main account page
            (self.family_url, "family"),    # Family account page
        ]
        
        for i, (base_url, account_type) in enumerate(urls_to_check):
            # Add random delay between account checks (except for first)
            if i > 0:
                await asyncio.sleep(random.uniform(0.5, 1.5))
            
            _LOGGER.info(f"Checking {account_type} page for reservations: {base_url}")
            
            try:
                # Get the page to find reservations
                async with self._session.get(base_url) as response:
                    response.raise_for_status()
                    text = await response.text()
                    _LOGGER.debug(f"Got response for {account_type} page, length: {len(text)}")
                
                soup = BeautifulSoup(text, 'html.parser')
                
                # First, check if this page has "Vorgemerkte Medien" section directly (family page)
                if 'Vorgemerkte Medien' in text:
                    _LOGGER.info(f"Found 'Vorgemerkte Medien' section directly on {account_type} page")
                    # Count how many times "vorgemerkt" appears to estimate number of reservations
                    vorgemerkt_count = text.lower().count('vorgemerkt')
                    medien_vorgemerkt_count = text.count('Medien vorgemerkt')
                    _LOGGER.info(f"Text contains 'vorgemerkt' {vorgemerkt_count} times, 'Medien vorgemerkt' {medien_vorgemerkt_count} times")
                    # Parse reservations directly from this page
                    reservations = self._parse_reservations_page(text)
                    _LOGGER.info(f"Parsed {len(reservations)} reservations from {account_type} page")
                else:
                    # Find reservations link
                    reservations_link = soup.find('a', href=lambda h: h and 'reservations' in h)
                    if not reservations_link:
                        _LOGGER.debug(f"No reservations link found on {account_type} page")
                        continue
                    
                    # Get the reservations URL
                    reservations_url = self.base_url.rstrip('/') + reservations_link.get('href')
                    
                    # Add small random delay before accessing reservations page
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    
                    # Navigate to reservations page
                    async with self._session.get(reservations_url) as response:
                        response.raise_for_status()
                        reservations_text = await response.text()
                    
                    # Parse reservations from this page
                    reservations = self._parse_reservations_page(reservations_text)
                    _LOGGER.info(f"Parsed {len(reservations)} reservations from {account_type} reservations page")
                
                # Process reservations
                for reservation in reservations:
                    res_id = reservation.get('reservation_id')
                    if res_id:
                        if res_id in reservations_by_id:
                            # Already seen - just add account type to found_on list
                            reservations_by_id[res_id]['found_on'].append(account_type)
                            _LOGGER.debug(f"Reservation found on multiple pages: {reservation.get('title')} (ID: {res_id})")
                        else:
                            # New reservation - add it
                            reservation['found_on'] = [account_type]
                            reservation['account'] = account_type  # Keep for backward compatibility
                            reservations_by_id[res_id] = reservation
                            all_reservations.append(reservation)
                
            except Exception as e:
                _LOGGER.error(f"Error fetching reserved media from {account_type}: {e}")
        
        return all_reservations
    
    def _parse_reservations_page(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse the reservations page to extract reserved media."""
        soup = BeautifulSoup(html_content, 'html.parser')
        reservations = []
        
        _LOGGER.info("Starting to parse reservations page")
        
        # First check if this is a family page with "Vorgemerkte Medien" section
        # Look for any h2, h3 or h4 with "Vorgemerkte Medien"
        reserved_headers = soup.find_all(['h2', 'h3', 'h4'], string=lambda text: text and 'Vorgemerkte Medien' in text)
        
        # Also check for headers that might have whitespace or be in a span
        if not reserved_headers:
            for header in soup.find_all(['h2', 'h3', 'h4']):
                header_text = header.get_text(strip=True)
                if header_text and 'Vorgemerkte Medien' in header_text:
                    reserved_headers.append(header)
                    _LOGGER.debug(f"Found header via text search: {header_text}")
        
        if reserved_headers:
            _LOGGER.info("Found 'Vorgemerkte Medien' section on page")
            # This is likely the family page with reserved media section
            for header in reserved_headers:
                _LOGGER.info(f"Processing header: {header.get_text(strip=True)}")
                # Find the next sibling div that contains the reserved items
                current = header.find_next_sibling()
                sibling_count = 0
                while current and sibling_count < 10:  # Limit iterations
                    sibling_count += 1
                    if hasattr(current, 'name'):
                        _LOGGER.debug(f"Sibling {sibling_count}: {current.name} with classes: {current.get('class', []) if hasattr(current, 'get') else 'N/A'}")
                        if current.name == 'div':
                            # Check for various possible classes for reservation listings
                            classes = current.get('class', [])
                            if any(cls in classes for cls in ['reader-listing', 'reader-listing-reservations', 'reader-listing-content', 'listing', 'listing-content']):
                                # Found the listing section
                                _LOGGER.info(f"Found listing section with classes: {classes}")
                                
                                # Process by account sections within this listing
                                current_account_number = None
                                # Look for direct children only to avoid duplicates
                                for element in current.find_all(['h4', 'div'], recursive=True):
                                    if element.name == 'h4' and 'reader-content-title' in element.get('class', []):
                                        # This is an account header
                                        header_text = element.get_text()
                                        _LOGGER.debug(f"Found reserved media header: {header_text}")
                                        match = re.search(r'Konto\s+Nr\.\s*(\d+)', header_text)
                                        if match:
                                            current_account_number = match.group(1)
                                            _LOGGER.info(f"Processing reserved items for account: {current_account_number}")
                                    elif element.name == 'div' and 'item' in element.get('class', []):
                                        # Check if this is a reservation variant
                                        if 'item-variant-reservation' in element.get('class', []):
                                            if current_account_number:
                                                reservation = self._extract_reservation_info(element)
                                                if reservation:
                                                    reservation['owner_number'] = current_account_number
                                                    reservation['owner_name'] = f'Leser {current_account_number}'
                                                    reservations.append(reservation)
                                                    _LOGGER.info(f"Found reserved item: '{reservation.get('title', 'Unknown')}' for account {current_account_number}")
                                break
                        elif current.name in ['h2', 'h3', 'h4']:
                            # Hit another section header, stop
                            break
                    current = current.find_next_sibling()
        
        # If we didn't find reservations yet, try another approach
        # Look for "Medien vorgemerkt" pattern anywhere in the page
        if not reservations:
            _LOGGER.info("Trying alternative parsing approach for reservations")
            # Find all text containing "Medien vorgemerkt"
            medien_vorgemerkt_pattern = re.compile(r'\d+\s+Medien\s+vorgemerkt')
            medien_vorgemerkt_texts = soup.find_all(text=medien_vorgemerkt_pattern)
            for text in medien_vorgemerkt_texts:
                _LOGGER.info(f"Found 'Medien vorgemerkt' text: {text.strip()}")
                # Extract account number from text like "Konto Nr. 687 | 1 Medien vorgemerkt"
                match = re.search(r'Konto\s+Nr\.\s*(\d+)', text)
                if match:
                    current_account_number = match.group(1)
                    _LOGGER.info(f"Found account {current_account_number} with reservations")
                    
                    # Try to extract title from the text itself (if in parentheses)
                    # Pattern: "1 Medien vorgemerkt (Title)"
                    title_match = re.search(r'\d+\s+Medien\s+vorgemerkt\s*\(([^)]+)\)', text)
                    if title_match:
                        title = title_match.group(1)
                        _LOGGER.info(f"Extracted title from text: {title}")
                        # Create a reservation entry even if we can't find the item div
                        reservation = {
                            'reservation_id': f'res_{current_account_number}_{len(reservations)+1}',
                            'title': title,
                            'author': '',
                            'position': 0,
                            'total_holds': 0,
                            'estimated_date': None,
                            'estimated_date_iso': None,
                            'reserved_since': '',
                            'reserved_since_iso': None,
                            'branch': '',
                            'cancelable': False,
                            'detail_url': None,
                            'owner_number': current_account_number,
                            'owner_name': f'Leser {current_account_number}'
                        }
                        reservations.append(reservation)
                        _LOGGER.info(f"Created reservation entry for: '{title}'")
                    
                    # Now look for items following this text
                    parent = text.parent
                    if parent:
                        # Look for following items
                        next_elem = parent.find_next_sibling()
                        while next_elem and hasattr(next_elem, 'name'):
                            if next_elem.name == 'div' and 'item' in next_elem.get('class', []):
                                reservation = self._extract_reservation_info(next_elem)
                                if reservation:
                                    reservation['owner_number'] = current_account_number
                                    reservation['owner_name'] = f'Leser {current_account_number}'
                                    reservations.append(reservation)
                                    _LOGGER.info(f"Found reserved item: '{reservation.get('title', 'Unknown')}'")
                            elif next_elem.name in ['h2', 'h3', 'h4']:
                                # Hit another header, stop
                                break
                            next_elem = next_elem.find_next_sibling()
        
        else:
            # Traditional reservations page parsing (for dedicated reservation pages)
            _LOGGER.debug("Using traditional reservations page parsing")
            # Look for item containers that are specifically reservations
            items = soup.find_all('div', class_='item')
            
            for item in items:
                # Skip message items
                if 'item-variant-message' in item.get('class', []):
                    continue
                
                # Only process items that are marked as reservations
                if 'item-variant-reservation' in item.get('class', []) or 'item-status-yellow' in item.get('class', []):
                    reservation = self._extract_reservation_info(item)
                    if reservation:
                        reservations.append(reservation)
        
        # Remove duplicates based on reservation_id
        unique_reservations = {}
        for res in reservations:
            res_id = res.get('reservation_id')
            if res_id:
                # If we already have this reservation, keep the one with owner info
                if res_id in unique_reservations:
                    existing = unique_reservations[res_id]
                    if not existing.get('owner_number') and res.get('owner_number'):
                        unique_reservations[res_id] = res
                else:
                    unique_reservations[res_id] = res
        
        final_reservations = list(unique_reservations.values())
        _LOGGER.info(f"Found {len(final_reservations)} unique reserved items total")
        for res in final_reservations:
            _LOGGER.debug(f"Reservation: {res.get('title', 'Unknown')} - Owner: {res.get('owner_number', 'None')} - Position: {res.get('position', 'N/A')}")
        return final_reservations
    
    def _extract_reservation_info(self, item: Tag) -> Optional[Dict[str, Any]]:
        """Extract reservation information from an item element."""
        try:
            reservation_info = {
                'reservation_id': item.get('id', ''),
                'title': '',
                'author': '',
                'position': 0,
                'total_holds': 0,
                'estimated_date': None,
                'estimated_date_iso': None,
                'reserved_since': '',
                'reserved_since_iso': None,
                'branch': '',
                'cancelable': False,
                'detail_url': None,
            }
            
            # Extract title and detail URL
            title_elem = item.find('div', class_='item-title')
            if title_elem:
                reservation_info['title'] = title_elem.text.strip()
                title_link = title_elem.find('a')
                if title_link and title_link.get('href'):
                    reservation_info['detail_url'] = self.base_url.rstrip('/') + title_link.get('href')
            else:
                # Try alternative: look for a link with the title
                title_link = item.find('a')
                if title_link and title_link.get_text(strip=True):
                    reservation_info['title'] = title_link.get_text(strip=True)
                    if title_link.get('href'):
                        reservation_info['detail_url'] = self.base_url.rstrip('/') + title_link.get('href')
                else:
                    # If still no title found, log the item HTML for debugging
                    _LOGGER.debug(f"No title found for item: {item.get('id', 'unknown')}")
                    _LOGGER.debug(f"Item HTML: {str(item)[:200]}...")
                    # Try to extract any text from the item
                    item_text = item.get_text(strip=True)
                    if item_text:
                        _LOGGER.debug(f"Item text content: {item_text[:100]}...")
                    return None
            
            # Extract author
            author_elem = item.find('div', class_='item-author')
            if author_elem:
                reservation_info['author'] = author_elem.text.strip()
            
            # Extract position in queue
            status_elem = item.find('div', class_='item-status')
            if status_elem:
                status_text = status_elem.text.strip()
                
                # Look for patterns like "Position 3 von 5" or "3. von 5"
                position_match = re.search(r'(?:Position\s*)?(\d+)\.?\s*(?:von|of)\s*(\d+)', status_text)
                if position_match:
                    reservation_info['position'] = int(position_match.group(1))
                    reservation_info['total_holds'] = int(position_match.group(2))
                    
                    # Estimate availability (very rough: 3 weeks per position)
                    if reservation_info['position'] > 0:
                        estimated_days = reservation_info['position'] * 21  # 3 weeks per position
                        estimated_date = datetime.now() + timedelta(days=estimated_days)
                        reservation_info['estimated_date'] = estimated_date.strftime('%d.%m.%Y')
                        reservation_info['estimated_date_iso'] = estimated_date.isoformat()
            
            # Extract reservation date
            date_elem = item.find('div', class_='item-date')
            if date_elem:
                date_text = date_elem.text.strip()
                reservation_info['reserved_since'] = date_text
                
                # Try to parse the date (assuming parse_german_date exists in main API class)
                if hasattr(self, 'parse_german_date'):
                    reserved_date = self.parse_german_date(date_text)
                    if reserved_date:
                        reservation_info['reserved_since_iso'] = datetime.combine(
                            reserved_date, 
                            datetime.min.time()
                        ).isoformat()
            
            # Extract branch
            branch_elem = item.find('div', class_='item-branch')
            if branch_elem:
                reservation_info['branch'] = branch_elem.text.strip()
            
            # Check if cancelable
            actions = item.find('div', class_='item-actions')
            if actions:
                cancel_action = actions.find(attrs={'data-action': 'cancel'})
                if cancel_action:
                    reservation_info['cancelable'] = True
            
            return reservation_info
            
        except Exception as e:
            _LOGGER.error("Error extracting reservation info: %s", e)
            return None
    
    async def cancel_reservation(self, reservation_id: str) -> Dict[str, Any]:
        """Cancel a reservation."""
        if not self.logged_in:
            _LOGGER.error("Not logged in")
            return {'success': False, 'message': 'Not logged in'}
        
        try:
            # This would need to be implemented based on the actual BibKat interface
            # Typically involves finding the cancel button/link and following it
            _LOGGER.warning("Cancel reservation not yet implemented")
            return {
                'success': False, 
                'message': 'Cancel reservation functionality not yet implemented'
            }
            
        except Exception as e:
            _LOGGER.error("Error canceling reservation: %s", e)
            return {'success': False, 'message': str(e)}