"""Renewal rules management for libraries."""
from __future__ import annotations

import logging
from datetime import datetime, date, timedelta
from typing import Dict, Optional, Any
import json
import os

_LOGGER = logging.getLogger(__name__)

class RenewalRulesManager:
    """Manages renewal rules for different libraries."""
    
    def __init__(self, hass):
        """Initialize the renewal rules manager."""
        self.hass = hass
        self._rules: Dict[str, Dict[str, Any]] = {}
        self._storage_path = hass.config.path("bibkat_renewal_rules.json")
        self._load_rules()
        
    def _load_rules(self) -> None:
        """Load renewal rules from storage."""
        try:
            if os.path.exists(self._storage_path):
                with open(self._storage_path, 'r') as f:
                    data = json.load(f)
                    # Convert ISO dates back to date objects
                    for library_url, rules in data.items():
                        if 'last_updated' in rules:
                            rules['last_updated'] = date.fromisoformat(rules['last_updated'])
                        self._rules[library_url] = rules
                    _LOGGER.info(f"Loaded renewal rules for {len(self._rules)} libraries")
        except Exception as e:
            _LOGGER.error(f"Error loading renewal rules: {e}")
            self._rules = {}
    
    def _save_rules(self) -> None:
        """Save renewal rules to storage."""
        try:
            # Convert date objects to ISO format for JSON
            data = {}
            for library_url, rules in self._rules.items():
                rules_copy = rules.copy()
                if 'last_updated' in rules_copy and isinstance(rules_copy['last_updated'], date):
                    rules_copy['last_updated'] = rules_copy['last_updated'].isoformat()
                data[library_url] = rules_copy
                
            with open(self._storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            _LOGGER.debug("Saved renewal rules")
        except Exception as e:
            _LOGGER.error(f"Error saving renewal rules: {e}")
    
    def get_renewal_offset_days(self, library_url: str) -> Optional[int]:
        """Get the renewal offset days for a library.
        
        Returns the number of days before due date when renewal becomes possible.
        """
        rules = self._rules.get(library_url, {})
        return rules.get('renewal_offset_days')
    
    def calculate_renewal_date(self, library_url: str, due_date: date) -> Optional[date]:
        """Calculate when a media item can be renewed based on library rules."""
        offset_days = self.get_renewal_offset_days(library_url)
        if offset_days is not None:
            return due_date - timedelta(days=offset_days)
        return None
    
    def update_rules(self, library_url: str, renewal_offset_days: int) -> None:
        """Update renewal rules for a library."""
        self._rules[library_url] = {
            'renewal_offset_days': renewal_offset_days,
            'last_updated': date.today(),
        }
        self._save_rules()
        _LOGGER.info(f"Updated renewal rules for {library_url}: offset={renewal_offset_days} days")
    
    def needs_update(self, library_url: str) -> bool:
        """Check if rules need to be updated (older than 7 days or missing)."""
        rules = self._rules.get(library_url, {})
        
        # No rules exist
        if 'renewal_offset_days' not in rules:
            return True
            
        # Check age
        last_updated = rules.get('last_updated')
        if not last_updated:
            return True
            
        # Update weekly
        days_old = (date.today() - last_updated).days
        return days_old >= 7
    
    def calculate_offset_from_dates(self, due_date: date, renewal_date: date) -> int:
        """Calculate the offset days from due date and renewal date."""
        return (due_date - renewal_date).days


class LibraryRenewalDetector:
    """Detects renewal rules for a library using browser automation."""
    
    def __init__(self, browser_service, library_url: str):
        """Initialize the detector."""
        self.browser_service = browser_service
        self.library_url = library_url
        
    async def detect_renewal_offset(self, username: str, password: str) -> Optional[int]:
        """Detect the renewal offset for the library.
        
        Finds a non-renewable media item and extracts the renewal date
        to calculate the offset from the due date.
        """
        try:
            # Use browser service to get media with renewal dates
            result = await self._find_media_with_renewal_info(username, password)
            
            if result and result.get('due_date') and result.get('renewal_date'):
                # Parse dates
                due_date = self._parse_date(result['due_date'])
                renewal_date = self._parse_date(result['renewal_date'])
                
                if due_date and renewal_date:
                    # Calculate offset
                    offset_days = (due_date - renewal_date).days
                    _LOGGER.info(
                        f"Detected renewal offset: {offset_days} days "
                        f"(due: {due_date}, renewable from: {renewal_date})"
                    )
                    return offset_days
                    
        except Exception as e:
            _LOGGER.error(f"Error detecting renewal offset: {e}")
            
        return None
    
    async def _find_media_with_renewal_info(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Find a media item with renewal date information."""
        # This would use the browser service to:
        # 1. Login
        # 2. Go to account/family page
        # 3. Find a non-renewable item
        # 4. Click renewal to get the modal
        # 5. Extract both due date and renewal date
        
        # For now, we'll use the existing browser service method
        # In a full implementation, this would be extended to also get the due date
        
        # Simplified version - would need to be extended
        _LOGGER.info("Detecting renewal rules using browser...")
        
        # Get any non-renewable media
        # This is a placeholder - actual implementation would scan all media
        # to find one with a renewal date modal
        
        return None  # Placeholder
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse German date format."""
        try:
            # Handle different formats
            if '.' in date_str:
                return datetime.strptime(date_str, '%d.%m.%Y').date()
            elif '-' in date_str:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
        return None