"""Dynamic template sensor registration for BibKat."""
from __future__ import annotations

import logging
from typing import Any, Dict
import os
import aiofiles

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers import storage

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _create_slot_sensor_config(slot_number: int) -> Dict[str, Any]:
    """Generate template configuration for a single slot."""
    index = slot_number - 1
    
    return {
        "name": f"Bibliothek Slot {slot_number}",
        "unique_id": f"bibkat_book_slot_{slot_number}",
        "state": Template(
            f"""{{%- set books = states.button 
               | selectattr('entity_id', 'match', 'button.bibkat_.*') 
               | rejectattr('attributes.media_id', 'undefined')
               | sort(attribute='attributes.days_remaining') | list -%}}
            {{{{ books[{index}].attributes.title if books[{index}] is defined else 'Leer' }}}}""",
            None
        ),
        "icon": Template(
            f"""{{%- set books = states.button 
               | selectattr('entity_id', 'match', 'button.bibkat_.*') 
               | rejectattr('attributes.media_id', 'undefined')
               | sort(attribute='attributes.days_remaining') | list -%}}
            {{%- if books[{index}] is defined -%}}
              {{%- set days = books[{index}].attributes.days_remaining -%}}
              {{%- if days < 0 -%}}mdi:book-alert
              {{%- elif days <= 3 -%}}mdi:book-clock
              {{%- else -%}}mdi:book-check
              {{%- endif -%}}
            {{%- else -%}}mdi:book-off-outline
            {{%- endif -%}}""",
            None
        ),
        "attributes": {
            "entity_id": Template(
                f"""{{%- set books = states.button 
                   | selectattr('entity_id', 'match', 'button.bibkat_.*') 
                   | rejectattr('attributes.media_id', 'undefined')
                   | sort(attribute='attributes.days_remaining') | list -%}}
                {{{{ books[{index}].entity_id if books[{index}] is defined else 'none' }}}}""",
                None
            ),
            "days_remaining": Template(
                f"""{{%- set books = states.button 
                   | selectattr('entity_id', 'match', 'button.bibkat_.*') 
                   | rejectattr('attributes.media_id', 'undefined')
                   | sort(attribute='attributes.days_remaining') | list -%}}
                {{{{ books[{index}].attributes.days_remaining if books[{index}] is defined else 999 }}}}""",
                None
            ),
            "author": Template(
                f"""{{%- set books = states.button 
                   | selectattr('entity_id', 'match', 'button.bibkat_.*') 
                   | rejectattr('attributes.media_id', 'undefined')
                   | sort(attribute='attributes.days_remaining') | list -%}}
                {{{{ books[{index}].attributes.author if books[{index}] is defined else '' }}}}""",
                None
            ),
            "account": Template(
                f"""{{%- set books = states.button 
                   | selectattr('entity_id', 'match', 'button.bibkat_.*') 
                   | rejectattr('attributes.media_id', 'undefined')
                   | sort(attribute='attributes.days_remaining') | list -%}}
                {{{{ books[{index}].attributes.account_alias if books[{index}] is defined else '' }}}}""",
                None
            ),
            "renewable": Template(
                f"""{{%- set books = states.button 
                   | selectattr('entity_id', 'match', 'button.bibkat_.*') 
                   | rejectattr('attributes.media_id', 'undefined')
                   | sort(attribute='attributes.days_remaining') | list -%}}
                {{{{ books[{index}].attributes.is_renewable_now if books[{index}] is defined else false }}}}""",
                None
            ),
            "due_date": Template(
                f"""{{%- set books = states.button 
                   | selectattr('entity_id', 'match', 'button.bibkat_.*') 
                   | rejectattr('attributes.media_id', 'undefined')
                   | sort(attribute='attributes.days_remaining') | list -%}}
                {{{{ books[{index}].attributes.due_date if books[{index}] is defined else '' }}}}""",
                None
            ),
        },
    }


def _create_statistics_sensor_configs() -> list[Dict[str, Any]]:
    """Create configuration for statistics sensors."""
    return [
        {
            "name": "Bibliothek Bücher Gesamt",
            "unique_id": "bibkat_total_books",
            "state": Template(
                """{{ states.button 
                   | selectattr('entity_id', 'match', 'button.bibkat_.*') 
                   | rejectattr('attributes.media_id', 'undefined')
                   | list | length }}""",
                None
            ),
            "unit_of_measurement": "Bücher",
            "icon": Template("mdi:bookshelf", None),
        },
        {
            "name": "Bibliothek Überfällige Bücher",
            "unique_id": "bibkat_overdue_books",
            "state": Template(
                """{{ states.button 
                   | selectattr('entity_id', 'match', 'button.bibkat_.*') 
                   | rejectattr('attributes.media_id', 'undefined')
                   | selectattr('attributes.days_remaining', 'lt', 0)
                   | list | length }}""",
                None
            ),
            "unit_of_measurement": "Bücher",
            "icon": Template("mdi:book-alert", None),
        },
        {
            "name": "Bibliothek Verlängerbare Bücher",
            "unique_id": "bibkat_renewable_books",
            "state": Template(
                """{{ states.button 
                   | selectattr('entity_id', 'match', 'button.bibkat_.*') 
                   | rejectattr('attributes.media_id', 'undefined')
                   | selectattr('attributes.is_renewable_now', 'eq', true)
                   | list | length }}""",
                None
            ),
            "unit_of_measurement": "Bücher",
            "icon": Template("mdi:book-refresh", None),
        },
        {
            "name": "Bibliothek Nächste Rückgabe",
            "unique_id": "bibkat_next_due",
            "state": Template(
                """{% set books = states.button 
                   | selectattr('entity_id', 'match', 'button.bibkat_.*') 
                   | rejectattr('attributes.media_id', 'undefined')
                   | sort(attribute='attributes.days_remaining') | list %}
                {{ books[0].attributes.days_remaining if books[0] is defined else 999 }}""",
                None
            ),
            "unit_of_measurement": "Tage",
            "icon": Template("mdi:calendar-clock", None),
            "attributes": {
                "title": Template(
                    """{% set books = states.button 
                       | selectattr('entity_id', 'match', 'button.bibkat_.*') 
                       | rejectattr('attributes.media_id', 'undefined')
                       | sort(attribute='attributes.days_remaining') | list %}
                    {{ books[0].attributes.title if books[0] is defined else 'Keine Bücher' }}""",
                    None
                ),
            },
        },
    ]


async def create_template_sensors(hass: HomeAssistant, force: bool = False) -> None:
    """Create and register all template sensors dynamically."""
    # Check if we already have a marker that sensors were created
    storage_key = f"{DOMAIN}.template_sensors_created"
    from homeassistant.helpers.storage import Store
    store = Store(hass, 1, storage_key)
    data = await store.async_load()
    
    # Check if file exists
    config_dir = hass.config.path()
    filename = os.path.join(config_dir, "bibkat_template_slots.yaml")
    file_exists = os.path.exists(filename)
    
    if not force and data and data.get("created") and file_exists:
        _LOGGER.debug("Template sensors already created and file exists")
        return
    
    if not file_exists:
        _LOGGER.info("Template sensor file not found, recreating...")
    
    # Generate the template sensor YAML content
    from .generate_templates import generate_full_template
    template_content = generate_full_template()
    
    # Write to file in config directory
    config_dir = hass.config.path()
    filename = os.path.join(config_dir, "bibkat_template_slots.yaml")
    
    try:
        async with aiofiles.open(filename, "w", encoding="utf-8") as f:
            await f.write(template_content)
        _LOGGER.info(f"Created template sensor file: {filename}")
        
        # Store marker that we created the file
        await store.async_save({"created": True})
        
        # Notify user to add to configuration
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "BibKat Template Sensoren erstellt",
                "message": (
                    f"Die Template-Sensoren wurden nach **{filename}** exportiert.\n\n"
                    "**Nächste Schritte:**\n\n"
                    "Fügen Sie folgende Zeile zu Ihrer configuration.yaml hinzu:\n"
                    "```yaml\n"
                    "template:\n"
                    "  - !include bibkat_template_slots.yaml\n"
                    "```\n\n"
                    "Wenn Sie bereits andere Template-Dateien haben:\n"
                    "```yaml\n"
                    "template:\n"
                    "  - !include ihre_andere_template.yaml\n"
                    "  - !include bibkat_template_slots.yaml\n"
                    "```\n\n"
                    "Nach dem Hinzufügen: **Home Assistant neu starten!**"
                ),
                "notification_id": "bibkat_template_created",
            }
        )
        
    except Exception as e:
        _LOGGER.error(f"Failed to create template sensor file: {e}")