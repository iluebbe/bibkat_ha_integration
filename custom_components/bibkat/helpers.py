"""Helper functions for BibKat integration."""
from __future__ import annotations

import logging
import os
import aiofiles
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

TEMPLATE_FILE = "bibkat_template_slots.yaml"


async def create_template_sensors(hass: HomeAssistant, force: bool = False, format_type: str = "include") -> bool:
    """Create template sensor configuration file.
    
    Args:
        hass: Home Assistant instance
        force: Force recreation even if file exists
        format_type: "include" for !include style, "merge_list" for !include_dir_merge_list style
        
    Returns:
        True if created successfully, False otherwise
    """
    config_dir = hass.config.path()
    
    # Determine file path based on format type
    if format_type == "merge_list":
        # Check if templates directory exists
        templates_dir = os.path.join(config_dir, "templates")
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir)
        template_file = os.path.join(templates_dir, "02_bibkat.yaml")
    else:
        template_file = os.path.join(config_dir, TEMPLATE_FILE)
    
    # Check if file already exists
    if os.path.exists(template_file) and not force:
        _LOGGER.info("Template file already exists: %s", template_file)
        return False
    
    try:
        # Generate template content based on format type
        if format_type == "merge_list":
            # Import the v2 generator for merge_list format
            from .generate_templates_v2 import generate_templates_merge_list
            template_content = generate_templates_merge_list()
        else:
            # Import the original generator
            from .generate_templates import generate_full_template
            template_content = generate_full_template()
        
        # Write to file
        async with aiofiles.open(template_file, 'w', encoding='utf-8') as f:
            await f.write(template_content)
        
        _LOGGER.info("Created template file: %s", template_file)
        
        # Show persistent notification with appropriate instructions
        if format_type == "merge_list":
            message = (
                f"Die Template-Sensoren wurden in `templates/02_bibkat.yaml` erstellt.\n\n"
                "**Ihre configuration.yaml verwendet bereits:**\n"
                "```yaml\n"
                "template: !include_dir_merge_list templates/\n"
                "```\n\n"
                "**Nächste Schritte:**\n"
                "1. Starten Sie Home Assistant neu\n"
                "2. Die Sensoren sind dann unter `sensor.bibliothek_slot_1` bis "
                "`sensor.bibliothek_slot_30` verfügbar"
            )
        else:
            message = (
                f"Die Template-Sensoren wurden in `{TEMPLATE_FILE}` erstellt.\n\n"
                "**Nächste Schritte:**\n"
                "1. Fügen Sie folgendes zu Ihrer `configuration.yaml` hinzu:\n"
                "   ```yaml\n"
                "   template:\n"
                f"     - !include {TEMPLATE_FILE}\n"
                "   ```\n"
                "2. Starten Sie Home Assistant neu\n"
                "3. Die Sensoren sind dann unter `sensor.bibliothek_slot_1` bis "
                "`sensor.bibliothek_slot_30` verfügbar"
            )
        
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "BibKat Template Sensoren erstellt",
                "message": message,
                "notification_id": "bibkat_template_created",
            }
        )
        
        return True
        
    except Exception as e:
        _LOGGER.error("Failed to create template file: %s", e)
        return False


def get_template_format_type(hass: HomeAssistant) -> str:
    """Detect which template format to use based on configuration.yaml.
    
    Returns:
        "merge_list" if !include_dir_merge_list is detected, "include" otherwise
    """
    config_file = hass.config.path("configuration.yaml")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if "!include_dir_merge_list templates" in content:
                return "merge_list"
    except Exception as e:
        _LOGGER.debug("Could not detect template format: %s", e)
    
    return "include"