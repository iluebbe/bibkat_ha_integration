"""BibKat Discovery Dashboard Generator."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import yaml
import aiofiles
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BibKatDiscoveryDashboard:
    """Generate a dynamic dashboard for BibKat using sections and template slots."""
    
    def __init__(self, hass: HomeAssistant):
        """Initialize the dashboard generator."""
        self.hass = hass
        
    async def async_discover(self) -> Dict[str, Any]:
        """Discover BibKat configuration."""
        discovery_info = {
            "has_template_slots": await self._check_template_slots(),
            "slot_count": await self._count_configured_slots(),
            "has_calendar": await self._check_calendar_entity(),
            "library_name": await self._get_library_name(),
            "has_reservations": await self._check_reservation_sensors(),
        }
        return discovery_info
    
    async def _check_template_slots(self) -> bool:
        """Check if template slots are configured."""
        # First check if sensors exist
        if self.hass.states.get("sensor.bibliothek_slot_1") is not None:
            return True
            
        # Check if template file exists
        import os
        template_file = self.hass.config.path("bibkat_template_slots.yaml")
        if os.path.exists(template_file):
            _LOGGER.info("Template file exists but sensors not loaded yet")
            return False
            
        return False
    
    async def _count_configured_slots(self) -> int:
        """Count how many template slots are configured."""
        count = 0
        for i in range(1, 31):
            if self.hass.states.get(f"sensor.bibliothek_slot_{i}"):
                count += 1
        return count
    
    async def _check_calendar_entity(self) -> bool:
        """Check if calendar entity exists."""
        # Check for any bibkat calendar entity
        for state in self.hass.states.async_all():
            if state.entity_id.startswith("calendar.bibkat_"):
                return True
        return False
    
    async def _get_library_name(self) -> str:
        """Get the library name from configured entities."""
        # Try to extract from calendar entity first
        for state in self.hass.states.async_all():
            if state.entity_id.startswith("calendar.bibkat_"):
                # Extract library name from entity_id like "calendar.bibkat_boehl_kalender"
                parts = state.entity_id.split("_")
                if len(parts) >= 3:
                    return parts[1].title()
        return "Bibliothek"
    
    async def _check_reservation_sensors(self) -> bool:
        """Check if reservation sensors exist."""
        for state in self.hass.states.async_all():
            if state.entity_id.startswith("sensor.bibkat_") and "vormerkungen" in state.entity_id:
                return True
        return False
    
    def generate_dashboard(self, discovery_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate dashboard configuration."""
        if discovery_info is None:
            discovery_info = {}
            
        library_name = discovery_info.get("library_name", "Bibliothek")
        max_slots = discovery_info.get("slot_count", 30)
        
        dashboard = {
            "type": "sections",
            "max_columns": 4,
            "title": library_name,
            "path": "bibliothek",
            "icon": "mdi:bookshelf",
            "sections": []
        }
        
        # Add header section
        dashboard["sections"].append(self._create_header_section(library_name))
        
        # Add sections based on discovery
        if discovery_info.get("has_calendar"):
            dashboard["sections"].append(self._create_calendar_section())
        
        dashboard["sections"].append(self._create_overview_section())
        dashboard["sections"].extend(self._create_book_sections(max_slots))
        dashboard["sections"].append(self._create_actions_section())
        
        if discovery_info.get("has_reservations"):
            dashboard["sections"].append(self._create_reservations_section())
        
        return dashboard
    
    def _create_header_section(self, library_name: str) -> Dict[str, Any]:
        """Create dashboard header with statistics."""
        return {
            "type": "grid",
            "cards": [{
                "type": "markdown",
                "content": f"""# 📚 {library_name} Dashboard

{{% set ns = namespace(total=0, overdue=0, due_soon=0, renewable=0) -%}}
{{% for i in range(1, 31) -%}}
  {{% set slot = 'sensor.bibliothek_slot_' ~ i -%}}
  {{% if states(slot) != 'Leer' -%}}
    {{% set ns.total = ns.total + 1 -%}}
    {{% set days = state_attr(slot, 'days_remaining') | int(999) -%}}
    {{% if days < 0 -%}}
      {{% set ns.overdue = ns.overdue + 1 -%}}
    {{% elif days <= 3 -%}}
      {{% set ns.due_soon = ns.due_soon + 1 -%}}
    {{% endif -%}}
    {{% if state_attr(slot, 'renewable') -%}}
      {{% set ns.renewable = ns.renewable + 1 -%}}
    {{% endif -%}}
  {{% endif -%}}
{{% endfor -%}}

**Status:** {{% if ns.overdue > 0 %}}🔴 {{{{ ns.overdue }}}} überfällig{{% if ns.due_soon > 0 %}} | {{% endif %}}{{% endif %}}{{% if ns.due_soon > 0 %}}🟡 {{{{ ns.due_soon }}}} bald fällig{{% endif %}}{{% if ns.overdue == 0 and ns.due_soon == 0 %}}✅ Alle Bücher pünktlich{{% endif %}}

📊 **{{{{ states('sensor.bibliothek_bucher_gesamt') | default(0) }}}}** ausgeliehen | **{{{{ states('sensor.bibliothek_verlangerbare_bucher') | default(0) }}}}** verlängerbar | **{{{{ states('sensor.bibliothek_vormerkungen_gesamt') | default(0) }}}}** vorgemerkt

---

ℹ️ **[Bibliothekskonto verwalten](../config/integrations/integration/bibkat)** | **[Benachrichtigungen](../config/integrations/integration/bibkat/config)**"""
            }]
        }
    
    def _create_calendar_section(self) -> Dict[str, Any]:
        """Create calendar section."""
        return {
            "type": "grid",
            "cards": [{
                "type": "calendar",
                "entities": self._find_calendar_entities(),
                "initial_view": "dayGridMonth"
            }]
        }
    
    def _find_calendar_entities(self) -> List[str]:
        """Find all BibKat calendar entities."""
        calendars = []
        if self.hass:
            for state in self.hass.states.async_all():
                if state.entity_id.startswith("calendar.bibkat_"):
                    calendars.append(state.entity_id)
        return calendars or ["calendar.bibkat_kalender"]
    
    def _create_overview_section(self) -> Dict[str, Any]:
        """Create overview section with statistics."""
        return {
            "type": "grid",
            "cards": [
                {
                    "type": "heading",
                    "heading": "📊 Übersicht",
                    "heading_style": "title"
                },
                {
                    "type": "tile",
                    "entity": "sensor.bibliothek_bucher_gesamt",
                    "name": "Gesamt",
                    "icon": "mdi:bookshelf"
                },
                {
                    "type": "tile",
                    "entity": "sensor.bibliothek_uberfallige_bucher",
                    "name": "Überfällig",
                    "icon": "mdi:book-alert",
                    "color": "red"
                },
                {
                    "type": "tile",
                    "entity": "sensor.bibliothek_verlangerbare_bucher",
                    "name": "Verlängerbar",
                    "icon": "mdi:book-refresh",
                    "color": "green"
                },
                {
                    "type": "tile",
                    "entity": "sensor.bibliothek_nachste_ruckgabe",
                    "name": "Nächste Rückgabe",
                    "icon": "mdi:calendar-clock",
                    "color": "orange"
                }
            ]
        }
    
    def _create_book_sections(self, max_slots: int) -> List[Dict[str, Any]]:
        """Create book sections grouped by urgency."""
        sections = []
        
        # Überfällige Bücher
        overdue_cards = [
            {
                "type": "heading",
                "heading": "🔴 Überfällige Bücher",
                "heading_style": "subtitle"
            }
        ]
        
        # Bald fällige Bücher
        due_soon_cards = [
            {
                "type": "heading",
                "heading": "🟡 Bald fällig (≤ 3 Tage)",
                "heading_style": "subtitle"
            }
        ]
        
        # Normale Bücher
        normal_cards = [
            {
                "type": "heading",
                "heading": "📚 Weitere Bücher",
                "heading_style": "subtitle"
            }
        ]
        
        # Create cards for all slots
        for i in range(1, max_slots + 1):
            slot_id = f"sensor.bibliothek_slot_{i}"
            
            # Overdue card
            overdue_cards.append({
                "type": "conditional",
                "conditions": [
                    {
                        "condition": "state",
                        "entity": f"binary_sensor.bibliothek_slot_{i}_uberfallig",
                        "state": "on"
                    }
                ],
                "card": self._create_book_entity_card(i)
            })
            
            # Due soon card
            due_soon_cards.append({
                "type": "conditional",
                "conditions": [
                    {
                        "condition": "state",
                        "entity": f"binary_sensor.bibliothek_slot_{i}_bald_fallig",
                        "state": "on"
                    }
                ],
                "card": self._create_book_entity_card(i)
            })
            
            # Normal card
            normal_cards.append({
                "type": "conditional",
                "conditions": [
                    {
                        "condition": "state",
                        "entity": f"binary_sensor.bibliothek_slot_{i}_normal",
                        "state": "on"
                    }
                ],
                "card": self._create_book_entity_card(i)
            })
        
        # Add sections with visibility conditions
        sections.append({
            "type": "grid",
            "cards": overdue_cards,
            "visibility": [{
                "condition": "template",
                "value_template": """{{ states.sensor 
                    | selectattr('entity_id', 'match', 'sensor.bibliothek_slot_.*')
                    | selectattr('state', '!=', 'Leer')
                    | map(attribute='attributes.days_remaining')
                    | map('int', 999)
                    | select('<', 0)
                    | list | length > 0 }}"""
            }]
        })
        
        sections.append({
            "type": "grid",
            "cards": due_soon_cards,
            "visibility": [{
                "condition": "template",
                "value_template": """{{ states.sensor 
                    | selectattr('entity_id', 'match', 'sensor.bibliothek_slot_.*')
                    | selectattr('state', '!=', 'Leer')
                    | map(attribute='attributes.days_remaining')
                    | map('int', 999)
                    | select('<=', 3)
                    | select('>=', 0)
                    | list | length > 0 }}"""
            }]
        })
        
        sections.append({
            "type": "grid",
            "cards": normal_cards,
            "visibility": [{
                "condition": "template",
                "value_template": """{{ states.sensor 
                    | selectattr('entity_id', 'match', 'sensor.bibliothek_slot_.*')
                    | selectattr('state', '!=', 'Leer')
                    | map(attribute='attributes.days_remaining')
                    | map('int', 999)
                    | select('>', 3)
                    | list | length > 0 }}"""
            }]
        })
        
        return sections
    
    def _create_book_entity_card(self, slot_number: int) -> Dict[str, Any]:
        """Create entity card for a book slot."""
        slot_id = f"sensor.bibliothek_slot_{slot_number}"
        
        return {
            "type": "entities",
            # No title - it's redundant since the book info is shown in the card
            "state_color": True,
            "show_header_toggle": False,
            "entities": [
                {
                    "entity": slot_id,
                    "name": "Status",
                    "secondary_info": "last-changed",
                    "icon": "mdi:book",
                    "tap_action": {
                        "action": "more-info"
                    }
                },
                {
                    "type": "attribute",
                    "entity": slot_id,
                    "attribute": "author",
                    "name": "Autor",
                    "icon": "mdi:account"
                },
                {
                    "type": "attribute",
                    "entity": slot_id,
                    "attribute": "due_date",
                    "name": "Rückgabe bis",
                    "icon": "mdi:calendar"
                },
                {
                    "type": "attribute",
                    "entity": slot_id,
                    "attribute": "days_remaining",
                    "name": "Verbleibende Tage",
                    "icon": "mdi:timer-sand"
                },
                {
                    "type": "attribute",
                    "entity": slot_id,
                    "attribute": "account",
                    "name": "Konto",
                    "icon": "mdi:account-circle"
                },
                {
                    "type": "divider"
                },
                {
                    "type": "buttons",
                    "entities": [{
                        "entity": slot_id,
                        "name": "Verlängern",
                        "icon": "mdi:refresh",
                        "tap_action": {
                            "action": "call-service",
                            "service": "button.press",
                            "data": {
                                "entity_id": f"{{{{ state_attr('{slot_id}', 'entity_id') }}}}"
                            },
                            "confirmation": {
                                "text": f"Möchten Sie dieses Buch verlängern?"
                            }
                        }
                    }]
                }
            ],
            "card_mod": {
                "style": """ha-card { 
                    border-left: 4px solid 
                    {% set days = state_attr(config.entity, 'days_remaining') %}
                    {% if days < 0 %}#f44336{% elif days <= 3 %}#ff9800{% else %}#4caf50{% endif %};
                    background: linear-gradient(to right, 
                    {% if days < 0 %}rgba(244, 67, 54, 0.1){% elif days <= 3 %}rgba(255, 152, 0, 0.1){% else %}rgba(76, 175, 80, 0.1){% endif %}, 
                    transparent);
                }"""
            }
        }
    
    def _create_actions_section(self) -> Dict[str, Any]:
        """Create actions section."""
        return {
            "type": "grid",
            "cards": [
                {
                    "type": "heading",
                    "heading": "🎯 Schnellaktionen",
                    "heading_style": "subtitle"
                },
                {
                    "type": "conditional",
                    "conditions": [{
                        "condition": "numeric_state",
                        "entity": "sensor.bibliothek_verlangerbare_bucher",
                        "above": 0
                    }],
                    "card": {
                        "type": "button",
                        "name": "Alle verlängerbaren Bücher verlängern",
                        "icon": "mdi:book-refresh-outline",
                        "tap_action": {
                            "action": "call-service",
                            "service": "bibkat.renew_all",
                            "confirmation": {
                                "text": "Alle verlängerbaren Bücher verlängern?"
                            }
                        },
                        "hold_action": {
                            "action": "more-info",
                            "entity": "sensor.bibliothek_verlangerbare_bucher"
                        }
                    }
                },
                {
                    "type": "button",
                    "name": "Test-Benachrichtigung",
                    "icon": "mdi:bell-check",
                    "tap_action": {
                        "action": "call-service",
                        "service": "bibkat.test_notification"
                    }
                }
            ]
        }
    
    def _create_reservations_section(self) -> Dict[str, Any]:
        """Create reservations section."""
        # Find the first reservation sensor
        reservation_entity = None
        for state in self.hass.states.async_all():
            if state.entity_id.startswith("sensor.bibkat_") and "vormerkungen" in state.entity_id:
                reservation_entity = state.entity_id
                break
        
        if not reservation_entity:
            reservation_entity = "sensor.bibkat_vormerkungen_total"
            
        return {
            "type": "grid",
            "cards": [
                {
                    "type": "heading",
                    "heading": "📋 Vormerkungen",
                    "heading_style": "subtitle"
                },
                {
                    "type": "tile",
                    "entity": reservation_entity,
                    "name": "Vormerkungen gesamt"
                }
            ],
            "visibility": [{
                "condition": "numeric_state",
                "entity": reservation_entity,
                "above": 0
            }]
        }
    
    async def export_dashboard(self, filename: str = "bibkat_dashboard.yaml") -> None:
        """Export dashboard to YAML file."""
        discovery_info = await self.async_discover()
        dashboard = self.generate_dashboard(discovery_info)
        
        # Write as YAML
        import os
        config_dir = self.hass.config.path()
        full_path = os.path.join(config_dir, filename)
        
        # Convert to YAML string
        yaml_content = yaml.dump(dashboard, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        # Write asynchronously
        async with aiofiles.open(full_path, "w", encoding="utf-8") as f:
            await f.write(yaml_content)
        
        _LOGGER.info(f"Exported BibKat dashboard to {full_path}")
        return full_path


# Service registration removed - dashboard generation now available through config flow only