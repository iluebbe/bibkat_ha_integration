"""Optional browser-based service for extracting renewal dates."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import re

_LOGGER = logging.getLogger(__name__)

# Optional imports
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    _LOGGER.info("Playwright not installed - browser mode disabled")


class BrowserService:
    """Optional browser service for complex operations."""
    
    def __init__(self, base_url: str):
        """Initialize browser service."""
        self.base_url = base_url.rstrip('/') + '/'
        self._browser = None
        self._context = None
        
    async def __aenter__(self):
        """Enter async context."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        await self.close()
        
    async def close(self):
        """Close browser."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
            
    async def is_available(self) -> bool:
        """Check if browser service is available."""
        return HAS_PLAYWRIGHT
        
    async def extract_renewal_date(
        self, 
        username: str, 
        password: str, 
        media_id: str
    ) -> Dict[str, Any]:
        """Extract renewal date using browser automation."""
        if not HAS_PLAYWRIGHT:
            return {
                'success': False,
                'error': 'Browser service not available - install playwright'
            }
            
        try:
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )
                
                # Create context with German locale
                context = await browser.new_context(
                    locale='de-DE',
                    viewport={'width': 1280, 'height': 720}
                )
                
                page = await context.new_page()
                
                # Set timeout
                page.set_default_timeout(15000)  # 15 seconds
                
                # Login
                _LOGGER.debug("Browser: Navigating to login page")
                await page.goto(f"{self.base_url}reader/")
                
                # Fill login form
                await page.fill('input[name="username"]', username)
                await page.fill('input[name="password"]', password)
                
                # Submit
                await page.press('input[name="password"]', 'Enter')
                
                # Wait for navigation
                await page.wait_for_load_state('networkidle')
                
                # Check login success
                if not await page.query_selector('a[href*="logout"]'):
                    _LOGGER.error("Browser: Login failed")
                    await browser.close()
                    return {'success': False, 'error': 'Login failed'}
                
                _LOGGER.debug("Browser: Login successful")
                
                # Go to family page
                await page.goto(f"{self.base_url}reader/family/")
                await page.wait_for_load_state('networkidle')
                
                # Find the media item
                media_selector = f'[data-id="{media_id}"], [id="media-{media_id}"]'
                media_element = await page.query_selector(media_selector)
                
                if not media_element:
                    _LOGGER.error(f"Browser: Media {media_id} not found")
                    await browser.close()
                    return {'success': False, 'error': 'Media not found'}
                
                # Extract due date from the media element
                due_date_text = None
                due_date_elem = await media_element.query_selector('.item-account-status')
                if due_date_elem:
                    due_date_text = await due_date_elem.text_content()
                    _LOGGER.debug(f"Browser: Found due date text: {due_date_text}")
                
                # Find renewal button
                renew_button = await media_element.query_selector('[data-action="renew"]')
                
                if renew_button:
                    # Media is renewable - click the button
                    _LOGGER.debug("Browser: Clicking renewal button")
                    await renew_button.click()
                    
                    # Wait for either success or modal
                    await page.wait_for_timeout(2000)  # Wait 2 seconds
                    
                    # Check for modal
                    modal = await page.query_selector('.tingle-modal')
                    
                    if modal:
                        _LOGGER.debug("Browser: Modal found, extracting text")
                        modal_text = await modal.text_content()
                        
                        # Extract renewal date
                        date_pattern = r'"([^"]+)"\s+kann erst ab dem\s+(\d{1,2}\.\d{1,2}\.\d{4})'
                        match = re.search(date_pattern, modal_text)
                        
                        if match:
                            title, date_str = match.groups()
                            _LOGGER.info(f"Browser: Found renewal date: {date_str}")
                            
                            # Parse dates
                            try:
                                parsed_renewal_date = datetime.strptime(date_str, '%d.%m.%Y').date()
                                result = {
                                    'success': True,
                                    'renewal_date': date_str,
                                    'renewal_date_iso': parsed_renewal_date.isoformat(),
                                    'book_title': title,
                                    'message': f'"{title}" kann erst ab dem {date_str} online verlängert werden.'
                                }
                                
                                # Add due date if we found it
                                if due_date_text:
                                    # Extract date from text like "Fällig am 15.07.2025"
                                    due_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', due_date_text)
                                    if due_match:
                                        due_str = due_match.group(1)
                                        parsed_due_date = datetime.strptime(due_str, '%d.%m.%Y').date()
                                        result['due_date'] = due_str
                                        result['due_date_iso'] = parsed_due_date.isoformat()
                                        
                                        # Calculate offset
                                        offset_days = (parsed_due_date - parsed_renewal_date).days
                                        result['renewal_offset_days'] = offset_days
                                        _LOGGER.info(f"Browser: Detected renewal offset: {offset_days} days")
                                
                                return result
                            except ValueError as e:
                                _LOGGER.error(f"Browser: Error parsing dates: {e}")
                    
                    # Check for success message
                    success_msg = await page.query_selector('.alert-success')
                    if success_msg:
                        return {
                            'success': True,
                            'renewed': True,
                            'message': 'Medium erfolgreich verlängert'
                        }
                else:
                    _LOGGER.info(f"Browser: No renewal button for media {media_id}")
                    return {
                        'success': False,
                        'error': 'Media not renewable',
                        'message': 'Medium kann nicht verlängert werden'
                    }
                
                await browser.close()
                return {'success': False, 'error': 'Could not extract renewal date'}
                
        except Exception as e:
            _LOGGER.error(f"Browser error: {e}")
            return {'success': False, 'error': str(e)}


async def test_browser_service():
    """Test the browser service."""
    service = BrowserService("https://www.bibkat.de/boehl/")
    
    if not await service.is_available():
        print("❌ Playwright not installed. Install with: pip install playwright && playwright install chromium")
        return
        
    result = await service.extract_renewal_date(
        username="687",
        password="aFaGKvVs4CZTEV", 
        media_id="21769866"
    )
    
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(test_browser_service())