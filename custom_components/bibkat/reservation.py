"""Reservation sensor entities for BibKat."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .account_manager import AccountManager, Library

# Import coordinator for runtime use
from .coordinator import BibKatMultiAccountCoordinator

_LOGGER: logging.Logger = logging.getLogger(__name__)


# This file only contains sensor class definitions
# The actual setup is done in sensor.py


class BibKatReservationCountSensor(CoordinatorEntity[BibKatMultiAccountCoordinator], SensorEntity):
    """Sensor showing total reservation count across all accounts."""
    
    _attr_has_entity_name: bool = False
    _attr_icon: str = "mdi:book-clock"
    
    def __init__(
        self,
        coordinator: BibKatMultiAccountCoordinator,
        library_name: str,
        library_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._library_name: str = library_name
        self._library_id: str = library_id
        self._attr_unique_id: str = f"bibkat_{library_id}_reservations_total"
        self._attr_name: str = f"BibKat {library_name} Vormerkungen"
        
        # Set device info
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, library_id)},
            name=f"BibKat {library_name}",
            manufacturer="BibKat",
            model="Bibliothek",
            configuration_url=coordinator.library_url,
        )
    
    @property
    def native_value(self) -> int:
        """Return the total number of reservations."""
        total: int = 0
        for account_data in self.coordinator.data.get("accounts", {}).values():
            reservations = account_data.get("reservations", [])
            total += len(reservations)
        return total
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        all_reservations: List[Dict[str, Any]] = []
        
        for account_id, account_data in self.coordinator.data.get("accounts", {}).items():
            reservations = account_data.get("reservations", [])
            for res in reservations:
                res_copy = res.copy()
                res_copy["account_id"] = account_id
                all_reservations.append(res_copy)
        
        # Sort by position
        all_reservations.sort(key=lambda x: x.get("position", 999))
        
        # Get translated attributes based on HA language
        lang = self.hass.config.language.lower()
        attrs = self._get_translated_attributes(lang, all_reservations)
        
        return attrs
    
    def _get_translated_attributes(self, lang: str, reservations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get translated attributes based on language."""
        if lang.startswith("de"):
            return {
                "vormerkungen": reservations,
                "anzahl_vormerkungen": len(reservations),
                "naechste_verfuegbar": self._get_next_available(reservations),
            }
        else:
            return {
                "reservations": reservations,
                "reservation_count": len(reservations),
                "next_available": self._get_next_available(reservations),
            }
    
    def _get_next_available(self, reservations: List[Dict[str, Any]]) -> Optional[str]:
        """Get the next available reservation."""
        for res in reservations:
            if res.get("position") == 1:
                return res.get("title")
        return None


class BibKatAccountReservationSensor(CoordinatorEntity[BibKatMultiAccountCoordinator], SensorEntity):
    """Sensor showing reservations for a specific account."""
    
    _attr_has_entity_name: bool = False
    _attr_icon: str = "mdi:book-clock-outline"
    
    def __init__(
        self,
        coordinator: BibKatMultiAccountCoordinator,
        account_id: str,
        account_name: str,
        library_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._account_id: str = account_id
        self._account_name: str = account_name
        self._library_name: str = library_name
        self._attr_unique_id: str = f"bibkat_{account_id}_reservations"
        self._attr_name: str = f"BibKat {library_name} {account_name} Vormerkungen"
        
        # Set device info
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, account_id)},
            name=f"{library_name} - {account_name}",
            manufacturer="BibKat",
            model="Bibliothekskonto",
        )
    
    @property
    def native_value(self) -> int:
        """Return the number of reservations for this account."""
        account_data: Dict[str, Any] = self.coordinator.data.get("accounts", {}).get(self._account_id, {})
        reservations: List[Dict[str, Any]] = account_data.get("reservations", [])
        return len(reservations)
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        account_data: Dict[str, Any] = self.coordinator.data.get("accounts", {}).get(self._account_id, {})
        reservations: List[Dict[str, Any]] = account_data.get("reservations", [])
        
        # Sort by position
        reservations.sort(key=lambda x: x.get("position", 999))
        
        # Get translated attributes
        lang = self.hass.config.language.lower()
        attrs = self._get_translated_attributes(lang, reservations)
        
        return attrs
    
    def _get_translated_attributes(self, lang: str, reservations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get translated attributes based on language."""
        if lang.startswith("de"):
            return {
                "vormerkungen": reservations,
                "anzahl": len(reservations),
                "naechste_position": self._get_next_position(reservations),
                "geschaetzte_verfuegbarkeit": self._get_estimated_availability(reservations),
            }
        else:
            return {
                "reservations": reservations,
                "count": len(reservations),
                "next_position": self._get_next_position(reservations),
                "estimated_availability": self._get_estimated_availability(reservations),
            }
    
    def _get_next_position(self, reservations: List[Dict[str, Any]]) -> Optional[int]:
        """Get the best position in queue."""
        if reservations:
            return min(res.get("position", 999) for res in reservations)
        return None
    
    def _get_estimated_availability(self, reservations: List[Dict[str, Any]]) -> Optional[str]:
        """Get the soonest estimated availability date."""
        dates = []
        for res in reservations:
            if res.get("estimated_date_iso"):
                dates.append(res["estimated_date_iso"])
        
        if dates:
            return min(dates)
        return None


# Note: BibKatReservationEntity was removed as it was unused
# If individual reservation entities are needed in the future,
# they should be created dynamically like the button entities