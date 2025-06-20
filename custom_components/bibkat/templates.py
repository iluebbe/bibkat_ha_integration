"""Message templates for BibKat notifications."""
from __future__ import annotations

from typing import Any, Dict, List

# Attribute translations
DE_ATTRIBUTES = {
    "borrowed_media": "ausgeliehene_medien",
    "title": "titel",
    "author": "autor",
    "due_date": "rueckgabe_bis",
    "due_date_iso": "rueckgabe_datum_iso",
    "days_remaining": "tage_verbleibend",
    "renewable": "verlaengerbar",
    "is_renewable_now": "jetzt_verlaengerbar",
    "media_id": "medien_id",
    "account": "konto",
    "account_alias": "konto_alias",
    "renewal_date": "verlaengerbar_ab",
    "renewal_date_iso": "verlaengerbar_ab_iso",
    "library": "bibliothek",
    "balance": "kontostand",
    "balance_currency": "waehrung",
    "card_expiry": "karte_gueltig_bis",
    "reservations": "vormerkungen",
    "accounts_summary": "konten_uebersicht",
    "next_due": "naechste_rueckgabe",
    "found_on": "gefunden_auf",
}

EN_ATTRIBUTES = {
    "borrowed_media": "borrowed_media",
    "title": "title",
    "author": "author", 
    "due_date": "due_date",
    "due_date_iso": "due_date_iso",
    "days_remaining": "days_remaining",
    "renewable": "renewable",
    "is_renewable_now": "is_renewable_now",
    "media_id": "media_id",
    "account": "account",
    "account_alias": "account_alias",
    "renewal_date": "renewal_date",
    "renewal_date_iso": "renewal_date_iso",
    "library": "library",
    "balance": "balance",
    "balance_currency": "currency",
    "card_expiry": "card_expiry",
    "reservations": "reservations",
    "accounts_summary": "accounts_summary",
    "next_due": "next_due",
    "found_on": "found_on",
}

# German templates
DE_TEMPLATES = {
    "due_soon_title": "{library}: {count} Medien bald fällig",
    "due_soon_header": "📚 {library} - Medien bald fällig:",
    "due_soon_item": """• {title}
  Fällig: {due_date} ({days_remaining} Tage)
  Konto: {account_alias}""",
    "due_soon_renewable": "  ✅ Kann jetzt verlängert werden",
    "due_soon_not_renewable": "  ⏰ Verlängerbar ab: {renewal_date}",
    
    "overdue_title": "{library}: {count} überfällige Medien!",
    "overdue_header": "⚠️ {library} - Überfällige Medien:",
    "overdue_item": """• {title}
  Fällig war: {due_date}
  Konto: {account_alias}""",
    
    "balance_title": "{library}: Hoher Kontostand",
    "balance_header": "💰 {library} - Hoher Kontostand:",
    "balance_item": "• {alias}: {balance:.2f} {currency}",
    "balance_threshold": "Schwellenwert: {threshold:.2f} EUR",
    
    "renewal_success_title": "✅ {library}: Verlängerung erfolgreich",
    "renewal_failed_title": "❌ {library}: Verlängerung fehlgeschlagen",
    "renewal_details_header": "Details:",
    "renewal_errors_header": "Fehler:",
    
    "test_title": "🔔 {library}: Test-Benachrichtigung",
    "test_message": """Dies ist eine Test-Benachrichtigung von der BibKat Integration.

Wenn Sie diese Nachricht sehen, funktionieren die Benachrichtigungen korrekt!""",
    
    "card_expiry_title": "{library}: Bibliothekskarte läuft bald ab",
    "card_expiry_message": """Die Bibliothekskarte für {account_alias} läuft am {expiry_date} ab.

Bitte erneuern Sie Ihre Karte rechtzeitig.""",
}

# English templates
EN_TEMPLATES = {
    "due_soon_title": "{library}: {count} items due soon",
    "due_soon_header": "📚 {library} - Items due soon:",
    "due_soon_item": """• {title}
  Due: {due_date} ({days_remaining} days)
  Account: {account_alias}""",
    "due_soon_renewable": "  ✅ Can be renewed now",
    "due_soon_not_renewable": "  ⏰ Renewable from: {renewal_date}",
    
    "overdue_title": "{library}: {count} overdue items!",
    "overdue_header": "⚠️ {library} - Overdue items:",
    "overdue_item": """• {title}
  Was due: {due_date}
  Account: {account_alias}""",
    
    "balance_title": "{library}: High account balance",
    "balance_header": "💰 {library} - High account balance:",
    "balance_item": "• {alias}: {balance:.2f} {currency}",
    "balance_threshold": "Threshold: {threshold:.2f} EUR",
    
    "renewal_success_title": "✅ {library}: Renewal successful",
    "renewal_failed_title": "❌ {library}: Renewal failed",
    "renewal_details_header": "Details:",
    "renewal_errors_header": "Errors:",
    
    "test_title": "🔔 {library}: Test notification",
    "test_message": """This is a test notification from the BibKat integration.

If you see this message, notifications are working correctly!""",
    
    "card_expiry_title": "{library}: Library card expiring soon",
    "card_expiry_message": """The library card for {account_alias} expires on {expiry_date}.

Please renew your card in time.""",
}


class MessageTemplate:
    """Helper class for formatting notification messages."""
    
    def __init__(self, language: str = "de") -> None:
        """Initialize with language."""
        self.templates = DE_TEMPLATES if language == "de" else EN_TEMPLATES
    
    def format_due_soon(
        self,
        library_name: str,
        items: List[Dict[str, Any]],
    ) -> tuple[str, str]:
        """Format due soon notification."""
        title = self.templates["due_soon_title"].format(
            library=library_name,
            count=len(items),
        )
        
        message_parts = [
            self.templates["due_soon_header"].format(library=library_name),
            "",
        ]
        
        for item in items:
            message_parts.append(
                self.templates["due_soon_item"].format(
                    title=item.get("title", "Unknown"),
                    due_date=item.get("due_date", "Unknown"),
                    days_remaining=item.get("days_remaining", 0),
                    account_alias=item.get("account_alias", "Unknown"),
                )
            )
            
            if item.get("is_renewable_now"):
                message_parts.append(self.templates["due_soon_renewable"])
            elif item.get("renewal_date"):
                message_parts.append(
                    self.templates["due_soon_not_renewable"].format(
                        renewal_date=item["renewal_date"]
                    )
                )
            
            message_parts.append("")  # Empty line between items
        
        return title, "\n".join(message_parts).strip()
    
    def format_overdue(
        self,
        library_name: str,
        items: List[Dict[str, Any]],
    ) -> tuple[str, str]:
        """Format overdue notification."""
        title = self.templates["overdue_title"].format(
            library=library_name,
            count=len(items),
        )
        
        message_parts = [
            self.templates["overdue_header"].format(library=library_name),
            "",
        ]
        
        for item in items:
            message_parts.append(
                self.templates["overdue_item"].format(
                    title=item.get("title", "Unknown"),
                    due_date=item.get("due_date", "Unknown"),
                    account_alias=item.get("account_alias", "Unknown"),
                )
            )
            message_parts.append("")  # Empty line between items
        
        return title, "\n".join(message_parts).strip()
    
    def format_balance(
        self,
        library_name: str,
        accounts: List[Dict[str, Any]],
        threshold: float,
    ) -> tuple[str, str]:
        """Format balance notification."""
        title = self.templates["balance_title"].format(library=library_name)
        
        message_parts = [
            self.templates["balance_header"].format(library=library_name),
            "",
        ]
        
        for account in accounts:
            message_parts.append(
                self.templates["balance_item"].format(
                    alias=account["alias"],
                    balance=account["balance"],
                    currency=account["currency"],
                )
            )
        
        message_parts.extend([
            "",
            self.templates["balance_threshold"].format(threshold=threshold),
        ])
        
        return title, "\n".join(message_parts)
    
    def format_renewal(
        self,
        library_name: str,
        result: Dict[str, Any],
    ) -> tuple[str, str]:
        """Format renewal notification."""
        if result.get("success"):
            title = self.templates["renewal_success_title"].format(library=library_name)
        else:
            title = self.templates["renewal_failed_title"].format(library=library_name)
        
        message_parts = [result.get("message", "")]
        
        if result.get("messages"):
            message_parts.extend([
                "",
                self.templates["renewal_details_header"],
            ])
            for msg in result["messages"]:
                message_parts.append(f"• {msg}")
        
        if result.get("errors"):
            message_parts.extend([
                "",
                self.templates["renewal_errors_header"],
            ])
            for err in result["errors"]:
                message_parts.append(f"• {err}")
        
        return title, "\n".join(message_parts)
    
    def format_test(self, library_name: str) -> tuple[str, str]:
        """Format test notification."""
        title = self.templates["test_title"].format(library=library_name)
        message = self.templates["test_message"]
        return title, message
    
    def format_card_expiry(
        self,
        library_name: str,
        account_alias: str,
        expiry_date: str,
    ) -> tuple[str, str]:
        """Format card expiry notification."""
        title = self.templates["card_expiry_title"].format(library=library_name)
        message = self.templates["card_expiry_message"].format(
            account_alias=account_alias,
            expiry_date=expiry_date,
        )
        return title, message