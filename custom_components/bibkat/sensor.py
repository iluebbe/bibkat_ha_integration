"""Sensor platform for BibKat with multi-account support."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ACCOUNT,
    ATTR_ACCOUNT_ALIAS,
    ATTR_AUTHOR,
    ATTR_BALANCE,
    ATTR_BALANCE_CURRENCY,
    ATTR_BORROWED_MEDIA,
    ATTR_CARD_EXPIRY,
    ATTR_DAYS_REMAINING,
    ATTR_DUE_DATE,
    ATTR_LIBRARY,
    ATTR_MEDIA_ID,
    ATTR_RENEWABLE,
    ATTR_RESERVATIONS,
    ATTR_TITLE,
    CONF_ACCOUNTS,
    CONF_LIBRARY_URL,
    DOMAIN,
)
from .templates import DE_ATTRIBUTES, EN_ATTRIBUTES

if TYPE_CHECKING:
    from .account_manager import Account, AccountManager, Library

# Import coordinator for runtime use
from .coordinator import BibKatMultiAccountCoordinator

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    from .account_manager import AccountManager, Library
    from .coordinator import BibKatMultiAccountCoordinator
    
    coordinator: BibKatMultiAccountCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    account_manager: AccountManager = hass.data[DOMAIN][config_entry.entry_id]["account_manager"]
    library_url: str = config_entry.data[CONF_LIBRARY_URL]
    
    entities: List[SensorEntity] = []
    
    # Get library
    library: Optional[Library] = account_manager.get_library(library_url)
    if not library:
        _LOGGER.error("Library not found for URL: %s", library_url)
        return
    
    # Create sensors for each account
    for account in library.accounts:
        # Borrowed media sensor
        entities.append(
            BorrowedMediaSensor(
                coordinator=coordinator,
                account=account,
                library_name=library.name,
            )
        )
        
        # Balance sensor
        entities.append(
            BalanceSensor(
                coordinator=coordinator,
                account=account,
                library_name=library.name,
            )
        )
    
    # Create combined sensor for all accounts
    entities.append(
        CombinedMediaSensor(
            coordinator=coordinator,
            library_name=library.name,
            library_id=library.id,
        )
    )
    
    # Add reservation sensors
    from .reservation import BibKatReservationCountSensor, BibKatAccountReservationSensor
    
    # Overall reservation count
    entities.append(
        BibKatReservationCountSensor(
            coordinator=coordinator,
            library_name=library.name,
            library_id=library.id,
        )
    )
    
    # Per-account reservation sensors
    for account in library.accounts:
        entities.append(
            BibKatAccountReservationSensor(
                coordinator=coordinator,
                account_id=account.id,
                account_name=account.display_name,
                library_name=library.name,
            )
        )
    
    # Also create sensors for unconfigured family members if they have data
    # These are discovered dynamically when we fetch data
    if coordinator.data:
        for account_id, account_data in coordinator.data.get("accounts", {}).items():
            # Check if this is an unconfigured account
            if not account_data.get("is_configured", True):  # Default True for backward compat
                # Use the account alias or default name
                account_name = account_data.get("account_alias", f"Leser {account_id}")
                
                # Create reservation sensor if they have reservations
                if account_data.get("reservations"):
                    entities.append(
                        BibKatAccountReservationSensor(
                            coordinator=coordinator,
                            account_id=account_id,
                            account_name=account_name,
                            library_name=library.name,
                        )
                    )
                    
                # Also create borrowed media sensor if they have borrowed items
                if account_data.get("total_borrowed", 0) > 0:
                    entities.append(
                        BibKatUnconfiguredAccountSensor(
                            coordinator=coordinator,
                            account_id=account_id,
                            account_name=account_name,
                            library_name=library.name,
                        )
                    )
    
    async_add_entities(entities, True)


class BorrowedMediaSensor(CoordinatorEntity[BibKatMultiAccountCoordinator], SensorEntity):
    """Sensor showing borrowed media for a single account."""

    _attr_has_entity_name: bool = False
    _attr_icon: str = "mdi:book-open-page-variant"

    def __init__(
        self,
        coordinator: "BibKatMultiAccountCoordinator",
        account: "Account",
        library_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._account: "Account" = account
        self._library_name: str = library_name
        
        # Set unique attributes
        self._attr_unique_id: str = f"bibkat_{account.id}_borrowed_media"
        self._attr_name: str = f"BibKat {library_name} {account.display_name} Ausgeliehene Medien"
        
        # Set device info
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, account.id)},
            name=f"{library_name} - {account.display_name}",
            manufacturer="BibKat",
            model="Bibliothekskonto",
        )
    
    def _get_translated_attributes(self) -> Dict[str, str]:
        """Get translated attribute names based on HA language."""
        # Get Home Assistant language
        language: str = self.hass.config.language or "en"
        
        # Return German attributes for German, English for everything else
        if language.lower().startswith("de"):
            return DE_ATTRIBUTES
        return EN_ATTRIBUTES

    @property
    def native_value(self) -> int:
        """Return the number of borrowed media."""
        account_data: Dict[str, Any] = self.coordinator.data.get("accounts", {}).get(self._account.id, {})
        return account_data.get("total_borrowed", 0)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "Medien"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        account_data: Dict[str, Any] = self.coordinator.data.get("accounts", {}).get(self._account.id, {})
        media_list: List[Dict[str, Any]] = account_data.get("borrowed_media", [])
        
        # Get translated attribute names
        attr_names: Dict[str, str] = self._get_translated_attributes()
        
        # Format media list for attributes
        formatted_media: List[Dict[str, Any]] = []
        for media in media_list:
            formatted_media.append({
                attr_names["title"]: media.get("title", ""),
                attr_names["author"]: media.get("author", ""),
                attr_names["due_date"]: media.get("due_date", ""),
                attr_names["due_date_iso"]: media.get("due_date_iso"),
                attr_names["days_remaining"]: media.get("days_remaining", 0),
                attr_names["renewable"]: media.get("renewable", False),
                attr_names["is_renewable_now"]: media.get("is_renewable_now", False),
                attr_names["media_id"]: media.get("media_id", ""),
                attr_names["account"]: media.get("account", ""),
                attr_names["renewal_date"]: media.get("renewal_date", ""),
                attr_names["renewal_date_iso"]: media.get("renewal_date_iso"),
                attr_names["found_on"]: media.get("found_on", []),
            })
        
        return {
            attr_names["borrowed_media"]: formatted_media,
            attr_names["account_alias"]: self._account.display_name,
            attr_names["library"]: self._library_name,
        }


class BibKatUnconfiguredAccountSensor(CoordinatorEntity[BibKatMultiAccountCoordinator], SensorEntity):
    """Sensor for unconfigured family member's borrowed media."""
    
    _attr_icon: str = "mdi:book-multiple"
    
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
        
        # Set unique attributes
        self._attr_unique_id: str = f"bibkat_{account_id}_borrowed_media"
        self._attr_name: str = f"BibKat {library_name} {account_name} Ausgeliehene Medien"
        
        # Set device info
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, account_id)},
            name=f"{library_name} - {account_name}",
            manufacturer="BibKat",
            model="Familienkonto",
        )
    
    def _get_translated_attributes(self) -> Dict[str, str]:
        """Get translated attribute names based on HA language."""
        # Get Home Assistant language
        language: str = self.hass.config.language or "en"
        
        # Return German attributes for German, English for everything else
        if language.lower().startswith("de"):
            return DE_ATTRIBUTES
        return EN_ATTRIBUTES

    @property
    def native_value(self) -> int:
        """Return the number of borrowed media."""
        account_data: Dict[str, Any] = self.coordinator.data.get("accounts", {}).get(self._account_id, {})
        return account_data.get("total_borrowed", 0)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "Medien"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return state attributes."""
        account_data: Dict[str, Any] = self.coordinator.data.get("accounts", {}).get(self._account_id, {})
        borrowed_media: List[Dict[str, Any]] = account_data.get("borrowed_media", [])
        
        # Get the right attribute names based on language
        attr_names: Dict[str, str] = self._get_translated_attributes()
        
        # Format media list for attributes
        formatted_media: List[Dict[str, Any]] = []
        for media in borrowed_media:
            formatted_media.append({
                attr_names["title"]: media.get("title", ""),
                attr_names["due_date"]: media.get("due_date", ""),
                attr_names["renewable"]: media.get("renewable", False),
                attr_names["days_remaining"]: media.get("days_remaining", 0),
            })
        
        return {
            attr_names["borrowed_media"]: formatted_media,
            attr_names["account_alias"]: self._account_name,
            attr_names["library"]: self._library_name,
            "is_configured": False,
        }


class BalanceSensor(CoordinatorEntity[BibKatMultiAccountCoordinator], SensorEntity):
    """Sensor showing account balance."""

    _attr_has_entity_name: bool = False
    _attr_icon: str = "mdi:currency-eur"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: "BibKatMultiAccountCoordinator",
        account: "Account",
        library_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._account: "Account" = account
        self._library_name: str = library_name
        
        # Set unique attributes
        self._attr_unique_id: str = f"bibkat_{account.id}_balance"
        self._attr_name: str = f"BibKat {library_name} {account.display_name} Kontostand"
        
        # Set device info (same as borrowed media sensor)
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, account.id)},
            name=f"{library_name} - {account.display_name}",
            manufacturer="BibKat",
            model="Bibliothekskonto",
        )
    
    def _get_translated_attributes(self) -> Dict[str, str]:
        """Get translated attribute names based on HA language."""
        # Get Home Assistant language
        language: str = self.hass.config.language or "en"
        
        # Return German attributes for German, English for everything else
        if language.lower().startswith("de"):
            return DE_ATTRIBUTES
        return EN_ATTRIBUTES

    @property
    def native_value(self) -> float:
        """Return the account balance."""
        account_data: Dict[str, Any] = self.coordinator.data.get("accounts", {}).get(self._account.id, {})
        balance_info: Dict[str, Any] = account_data.get("balance_info", {})
        return balance_info.get("balance", 0.0)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        account_data: Dict[str, Any] = self.coordinator.data.get("accounts", {}).get(self._account.id, {})
        balance_info: Dict[str, Any] = account_data.get("balance_info", {})
        return balance_info.get("currency", "EUR")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        account_data: Dict[str, Any] = self.coordinator.data.get("accounts", {}).get(self._account.id, {})
        balance_info: Dict[str, Any] = account_data.get("balance_info", {})
        
        # Get translated attribute names
        attr_names: Dict[str, str] = self._get_translated_attributes()
        
        return {
            attr_names["balance"]: balance_info.get("balance", 0.0),
            attr_names["balance_currency"]: balance_info.get("currency", "EUR"),
            attr_names["card_expiry"]: balance_info.get("card_expiry"),
            attr_names["reservations"]: balance_info.get("reservations", 0),
            attr_names["account_alias"]: self._account.display_name,
            attr_names["library"]: self._library_name,
        }


class CombinedMediaSensor(CoordinatorEntity[BibKatMultiAccountCoordinator], SensorEntity):
    """Sensor showing combined borrowed media from all accounts."""

    _attr_has_entity_name: bool = False
    _attr_icon: str = "mdi:book-multiple"

    def __init__(
        self,
        coordinator: "BibKatMultiAccountCoordinator",
        library_name: str,
        library_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._library_name: str = library_name
        self._library_id: str = library_id
        
        # Set unique attributes
        self._attr_unique_id: str = f"bibkat_{library_id}_all_borrowed_media"
        self._attr_name: str = f"BibKat {library_name} Alle Ausgeliehene Medien"
        
        # Set device info
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, library_id)},
            name=f"BibKat {library_name}",
            manufacturer="BibKat",
            model="Bibliothek",
            configuration_url=coordinator.library_url,
        )
    
    def _get_translated_attributes(self) -> Dict[str, str]:
        """Get translated attribute names based on HA language."""
        # Get Home Assistant language
        language: str = self.hass.config.language or "en"
        
        # Return German attributes for German, English for everything else
        if language.lower().startswith("de"):
            return DE_ATTRIBUTES
        return EN_ATTRIBUTES

    @property
    def native_value(self) -> int:
        """Return the total number of borrowed media across all accounts."""
        return self.coordinator.data.get("total_borrowed", 0)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "Medien"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        all_media: List[Dict[str, Any]] = self.coordinator.data.get("all_media", [])
        
        # Get translated attribute names
        attr_names: Dict[str, str] = self._get_translated_attributes()
        
        # Format media list for attributes
        formatted_media: List[Dict[str, Any]] = []
        for media in all_media:
            formatted_media.append({
                attr_names["title"]: media.get("title", ""),
                attr_names["author"]: media.get("author", ""),
                attr_names["due_date"]: media.get("due_date", ""),
                attr_names["due_date_iso"]: media.get("due_date_iso"),
                attr_names["days_remaining"]: media.get("days_remaining", 0),
                attr_names["renewable"]: media.get("renewable", False),
                attr_names["is_renewable_now"]: media.get("is_renewable_now", False),
                attr_names["media_id"]: media.get("media_id", ""),
                attr_names["account"]: media.get("account", ""),
                attr_names["account_alias"]: media.get("account_alias", ""),
                attr_names["renewal_date"]: media.get("renewal_date", ""),
                attr_names["renewal_date_iso"]: media.get("renewal_date_iso"),
                attr_names["found_on"]: media.get("found_on", []),
                "is_configured": media.get("is_configured", True),
                "is_family_only": media.get("found_on", []) == ["family"],
            })
        
        # Count media per account
        accounts_summary: Dict[str, int] = {}
        unconfigured_summary: Dict[str, int] = {}
        
        for media in all_media:
            account_alias: str = media.get("account_alias", "Unknown")
            if not media.get("is_configured", True):  # Default True for backward compat
                # Track unconfigured accounts separately
                unconfigured_summary[account_alias] = unconfigured_summary.get(account_alias, 0) + 1
            else:
                accounts_summary[account_alias] = accounts_summary.get(account_alias, 0) + 1
        
        attrs = {
            attr_names["borrowed_media"]: formatted_media,
            attr_names["library"]: self._library_name,
            attr_names["accounts_summary"]: accounts_summary,
            attr_names["next_due"]: formatted_media[0] if formatted_media else None,
        }
        
        # Add unconfigured accounts summary if any
        if unconfigured_summary:
            attrs[attr_names.get("unconfigured_accounts_summary", "unconfigured_accounts_summary")] = unconfigured_summary
            
        return attrs