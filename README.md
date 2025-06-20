# BibKat Bibliothek Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/yourusername/bibkat_ha_integration.svg?style=for-the-badge)](https://github.com/yourusername/bibkat_ha_integration/releases)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Community](https://img.shields.io/badge/Community-Forum-blue?style=for-the-badge)](https://community.home-assistant.io/)

Eine professionelle Home Assistant Integration für BibKat Bibliotheken mit Multi-Account-Support, automatischen Benachrichtigungen und Actionable Notifications. Unterstützt alle BibKat-Bibliotheken deutschlandweit.

## 🌟 Features

### Kern-Features
✅ **Multi-Bibliothek Support** - Unterstützt alle BibKat-Bibliotheken  
✅ **Multi-Account pro Bibliothek** - Mehrere Leserkonten (Familie) verwalten  
✅ **Sensoren pro Account** - Getrennte Übersicht für jedes Familienmitglied  
✅ **Kombinierter Sensor** - Gesamtübersicht aller Konten  
✅ **Kontostand-Tracking** - Gebühren, Kartenablauf, Vormerkungen  
✅ **Vormerkungen/Reservierungen** - Tracking vorgemerkter Medien mit Position  

### Intelligente Funktionen
✅ **Exakte Datumsberechnung** - Präzise Tage bis zur Rückgabe  
✅ **Verlängerungserkennung** - Zeigt an, wann Medien verlängerbar sind  
✅ **Verlängerungsdatum-Extraktion** - Automatisch aus Server-Antwort  
✅ **ISO-Datumsformat** - Für Automatisierungen und Sortierung  
✅ **Familienkonten** - Automatische Erkennung verknüpfter Konten  
✅ **Externe Familienmitglieder** - Bücher von nicht konfigurierten Konten  
✅ **Auto-Update Verlängerungsdatum** - Bei jedem Verlängerungsversuch  

### Benachrichtigungen & Aktionen
✅ **Actionable Notifications** - Verlängern direkt aus der Benachrichtigung!  
✅ **Smart Actions** - Buttons nur wenn Verlängerung möglich  
✅ **Automatische Checks** - Alle 6 Stunden Prüfung (1x täglich Details)  
✅ **Konfigurierbare Schwellenwerte** - Wann soll benachrichtigt werden  
✅ **Multi-Language** - Deutsche und englische Templates  

### Services
✅ **Verlängerung** - Alle oder einzelne Konten verlängern  
✅ **Test-Benachrichtigung** - Notification-Setup prüfen  

### Calendar Integration 📅
✅ **Native Kalender** - Fälligkeiten im Home Assistant Kalender  
✅ **Verlängerungs-Erinnerungen** - 3 Tage vor Fälligkeit  
✅ **Farbcodierte Events** - Nach Dringlichkeit (überfällig, heute, bald)  
✅ **Kombinierter Kalender** - Alle Konten in einer Ansicht  

### Discovery Dashboard 📚 (NEU in v0.7.0)
✅ **Auto-generiertes Dashboard** - Übersichtliche Medienverwaltung  
✅ **30 Template-Sensoren** - Stabile UI-Referenzen für dynamische Medien  
✅ **Automatische Sortierung** - Nach Fälligkeit (überfällig, bald fällig, normal)  
✅ **Farbcodierte Karten** - Visuelle Dringlichkeitsanzeige  
✅ **One-Click Verlängerung** - Alle verlängerbaren Bücher auf einmal  
✅ **Statistik-Übersicht** - Gesamtzahl, überfällige, verlängerbare Bücher  

## 📦 Installation

### HACS (empfohlen)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=yourusername&repository=bibkat_ha_integration&category=integration)

#### Option 1: Mit My Home Assistant Link
1. Klicke den Button oben ↑
2. HACS öffnet sich automatisch mit diesem Repository
3. Klicke "Download" → "Download" → Wähle die neueste Version
4. Starte Home Assistant neu

#### Option 2: Manuell in HACS
1. HACS öffnen
2. Integrationen → Menü (3 Punkte oben rechts) → Custom repositories
3. Repository URL: `https://github.com/yourusername/bibkat_ha_integration`
4. Kategorie: `Integration`
5. "Add" klicken
6. Das neue Repository "BibKat Bibliothek" suchen und öffnen
7. "Download" klicken → Neueste Version wählen
8. Home Assistant neustarten

### Manuell (ohne HACS)
1. Lade die neueste Version von [GitHub Releases](https://github.com/yourusername/bibkat_ha_integration/releases) herunter
2. Entpacke die ZIP-Datei
3. Kopiere den `custom_components/bibkat` Ordner in dein Home Assistant `config/custom_components/` Verzeichnis
4. Die Struktur sollte so aussehen:
   ```
   config/
   └── custom_components/
       └── bibkat/
           ├── __init__.py
           ├── manifest.json
           └── ...
   ```
5. Starte Home Assistant neu

### Nach der Installation
1. Gehe zu **Einstellungen** → **Geräte & Dienste**
2. Klicke auf **"+ Integration hinzufügen"**
3. Suche nach **"BibKat"**
4. Folge den Konfigurationsschritten

## 🔧 Konfiguration

### Schritt 1: Bibliothek hinzufügen
1. **Bibliotheks-URL** eingeben (z.B. `https://www.bibkat.de/boehl/`)
2. **Erstes Konto** hinzufügen:
   - Lesernummer
   - Passwort
   - Alias (z.B. "Hauptkonto")
3. **Weitere Konten** optional hinzufügen (Checkbox "Weiteres Konto hinzufügen")

### Schritt 2: Dashboard & Template-Sensoren (NEU)
In den Integrationsoptionen unter "Features":
- **Template-Sensoren erstellen**: Aktivieren für erweiterte Dashboard-Funktionen
- **Dashboard erstellen**: Generiert ein vorkonfiguriertes Dashboard

Nach der Erstellung:
1. Fügen Sie `template: - !include bibkat_template_slots.yaml` zu Ihrer configuration.yaml hinzu
2. Starten Sie Home Assistant neu
3. Laden Sie das Dashboard unter Einstellungen → Dashboards → Dashboard hinzufügen

### Schritt 3: Benachrichtigungen konfigurieren (Optional)
In den Integrationsoptionen:
- **Benachrichtigungsdienst** auswählen (z.B. `notify.mobile_app_phone`)
- **Schwellenwerte** setzen:
  - Tage vor Fälligkeit: 1-14 Tage
  - Kontostand-Warnung: EUR-Betrag
- **Benachrichtigungstypen** aktivieren/deaktivieren
- **Kalender-Optionen**:
  - "Erstelle separate Kalender pro Account" - Nur aktivieren wenn gewünscht (sonst doppelte Events!)

### Unterstützte Bibliotheken
Alle BibKat-Bibliotheken werden unterstützt:
- KÖB Böhl: `https://www.bibkat.de/boehl/`
- Kreuth: `https://www.bibkat.de/kreuth/`
- Deine lokale Bibliothek: `https://www.bibkat.de/DEINE_BIBLIOTHEK/`

## 📊 Sensoren & Entitäten

### Individuelle Buch-Entitäten (NEU in v0.5.0)
Jedes ausgeliehene Buch wird als eigene Button-Entity erstellt:
- `button.bibkat_[bibliothek]_[buchtitel]_[id]` - Ein Buch
- **Press = Verlängern!** (wenn verlängerbar)
- Automatisch erstellt/gelöscht beim Ausleihen/Zurückgeben

Beispiel:
```yaml
button.bibkat_boehl_harry_potter_12345:
  state: "on"  # = verlängerbar
  attributes:
    title: "Harry Potter und der Stein der Weisen"
    author: "J.K. Rowling"
    days_remaining: 5
    account_alias: "Hauptkonto"
    renewal_date: "06.07.2025"  # NEU!
    renewal_date_formatted: "06.07.2025"
    days_until_renewable: 21  # NEU!
```

### Pro Account Sensoren
- `sensor.bibkat_[bibliothek]_[account]_ausgeliehene_medien` - Anzahl ausgeliehener Medien
- `sensor.bibkat_[bibliothek]_[account]_kontostand` - Aktueller Kontostand

### Kombinierte Sensoren
- `sensor.bibkat_[bibliothek]_alle_ausgeliehene_medien` - Alle Medien aller Konten

### Template Slots (für Dashboards)
Füge dies zu deiner `configuration.yaml` hinzu:
```yaml
template: !include custom_components/bibkat/template_slots_full.yaml
```

Dies erstellt 20 stabile Slot-Sensoren für Dashboards:
- `sensor.bibkat_book_slot_1` bis `sensor.bibkat_book_slot_20`
- Automatisch gefüllt mit Büchern nach Dringlichkeit
- Leere Slots zeigen "Leer"

### Kalender-Entitäten
**Gesamt-Kalender**: `calendar.bibkat_[bibliothek]_kalender`
- Alle Fälligkeiten und Erinnerungen
- Farbcodierte Events nach Dringlichkeit

**Konto-Kalender**: `calendar.bibkat_[bibliothek]_[konto]_kalender` *(Optional)*
- Pro-Konto Ansicht für Familien
- Nur Events des jeweiligen Kontos
- ⚠️ **Hinweis**: Zeigt die gleichen Events wie der Gesamt-Kalender. Aktiviere diese Option nur, wenn du separate Kalender pro Familienmitglied möchtest. Sonst siehst du alle Events doppelt!

### Sensor-Attribute
```yaml
borrowed_media:
  - title: "Das kleine Gespenst"
    author: "Otfried Preußler"
    due_date: "Rückgabe bis: So., 13. Jul."
    due_date_iso: "2025-07-13"  # Für Automatisierungen
    days_remaining: 25
    renewable: true
    renewal_date: "30.06.2025"  # NEU! Wann verlängerbar
    renewal_date_iso: "2025-06-30"
    is_renewable_now: false  # Wird true wenn verlängerbar
    account: "family"
    account_alias: "Kinderkonto"
    external_account: false  # true für nicht konfigurierte Familienmitglieder
```

### Reservierungs-Sensoren
- `sensor.bibkat_[bibliothek]_vormerkungen` - Gesamtzahl aller Vormerkungen
- `sensor.bibkat_[bibliothek]_[account]_vormerkungen` - Vormerkungen pro Konto

**Attribute:**
```yaml
vormerkungen:
  - title: "Die drei ??? - Das Gespensterschloss"
    author: "Robert Arthur"
    position: 3  # Position in der Warteliste
    total_holds: 5  # Gesamtzahl der Vormerkungen
    estimated_date: "15.08.2025"  # Geschätzte Verfügbarkeit
    reserved_since: "01.06.2025"
    branch: "Hauptstelle"
```

### Template-Sensoren (NEU in v0.7.0)
Die Integration erstellt automatisch 30 Template-Sensoren als "Slots" für die Mediendarstellung:
- `sensor.bibliothek_slot_1` bis `sensor.bibliothek_slot_30`
- `sensor.bibliothek_bucher_gesamt` - Gesamtzahl ausgeliehener Bücher
- `sensor.bibliothek_uberfallige_bucher` - Anzahl überfälliger Bücher
- `sensor.bibliothek_verlangerbare_bucher` - Anzahl verlängerbarer Bücher
- `sensor.bibliothek_nachste_ruckgabe` - Tage bis zur nächsten Rückgabe
- `sensor.bibliothek_vormerkungen_gesamt` - Gesamtzahl der Vormerkungen

Diese Sensoren ermöglichen das Discovery Dashboard mit stabilen UI-Referenzen.

## 🔔 Actionable Notifications

### Beispiel-Benachrichtigung
```
📚 Böhl: 3 Medien bald fällig

• Das kleine Gespenst
  Fällig: So., 13. Jul. (2 Tage)
  Konto: Kinderkonto
  ✅ Kann jetzt verlängert werden

[📚 Alle 1 verlängern] [📗 Kinderkonto (1)] [📖 Details]
```

**Ein Tap → Verlängerung → Erfolgsmeldung!**

### Notification Actions
- **"Alle X verlängern"** - Nur wenn Medien verlängerbar sind
- **"[Konto] (X)"** - Pro-Konto-Verlängerung bei mehreren Konten
- **"Details anzeigen"** - Öffnet Dashboard in HA
- **"Versuche Verlängerung"** - Bei überfälligen Medien

## 🛠️ Services

### bibkat.renew_all
```yaml
service: bibkat.renew_all
data:
  account_id: "boehl_689"  # Optional - für spezifisches Konto
```

### bibkat.test_notification
```yaml
service: bibkat.test_notification
data:
  library_url: "https://www.bibkat.de/boehl/"  # Optional
```

## 🤖 Automatisierungen

### Intelligente Auto-Verlängerung
```yaml
automation:
  - alias: "BibKat - Auto-Verlängerung wenn möglich"
    trigger:
      - platform: state
        entity_id: sensor.bibkat_boehl_alle_ausgeliehene_medien
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.bibkat_boehl_alle_ausgeliehene_medien', 'borrowed_media')
             | selectattr('is_renewable_now', 'eq', true)
             | list | length > 0 }}
    action:
      - service: bibkat.renew_all
      - service: notify.mobile_app_phone
        data:
          title: "📚 Auto-Verlängerung"
          message: "Verlängere verlängerbare Medien..."
```

### Erweiterte Fälligkeitswarnung
```yaml
automation:
  - alias: "BibKat - Erweiterte Fälligkeitswarnung"
    trigger:
      - platform: time
        at: "09:00:00"
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.bibkat_boehl_alle_ausgeliehene_medien', 'borrowed_media')
             | selectattr('days_remaining', 'le', 3)
             | selectattr('days_remaining', 'gt', 0)
             | list | length > 0 }}
    action:
      - service: notify.mobile_app_phone
        data:
          title: "📚 Medien bald fällig!"
          message: >
            {% set items = state_attr('sensor.bibkat_boehl_alle_ausgeliehene_medien', 'borrowed_media')
               | selectattr('days_remaining', 'le', 3) | list %}
            {{ items | length }} Medien in 3 Tagen fällig!
            {% for item in items[:3] %}
            • {{ item.title }} ({{ item.days_remaining }}d)
            {%- endfor %}
          data:
            actions:
              - action: "renew_due_soon"
                title: "📗 Jetzt verlängern"
```

Weitere Beispiele im `examples/automations.yaml`!

## 🌍 Multi-Language Support

Die Integration unterstützt:
- 🇩🇪 Deutsch (Standard)
- 🇬🇧 Englisch

Benachrichtigungen und Sensor-Attribute passen sich automatisch an die HA-Spracheinstellung an.

### Automatische Attribut-Übersetzung
Ab v0.3.1 werden Sensor-Attribute automatisch übersetzt:
- Deutsche HA-Installation → Deutsche Attribute (`ausgeliehene_medien`, `titel`, etc.)
- Englische HA-Installation → Englische Attribute (`borrowed_media`, `title`, etc.)

Siehe [ATTRIBUTE_TRANSLATION.md](ATTRIBUTE_TRANSLATION.md) für Details.

## 📈 Dashboard-Beispiel

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Bibliothek Böhl
    entities:
      - entity: sensor.bibkat_boehl_alle_ausgeliehene_medien
        name: Gesamt ausgeliehen
      - entity: sensor.bibkat_boehl_hauptkonto_ausgeliehene_medien
        name: Hauptkonto
      - entity: sensor.bibkat_boehl_kinderkonto_ausgeliehene_medien
        name: Kinderkonto
      - entity: sensor.bibkat_boehl_hauptkonto_kontostand
        name: Gebühren
        
  - type: markdown
    content: >
      {% set media = state_attr('sensor.bibkat_boehl_alle_ausgeliehene_medien', 'borrowed_media') %}
      {% if media %}
      **Nächste Rückgaben:**
      {% for item in media[:5] %}
      - {{ item.title }} - {{ item.days_remaining }} Tage ({{ item.account_alias }})
      {% endfor %}
      {% endif %}
```

## 🔧 Technische Details

- **Update-Intervall**: 6 Stunden (Hauptdaten), 24 Stunden (Verlängerungsdetails)
- **Architektur**: Multi-Account mit Account Manager
- **Persistenz**: Konten werden gespeichert
- **Rate Limiting**: 0.5-1.5s zwischen API-Calls (human-like)
- **Authentifizierung**: Session-basiert mit CSRF-Token
- **Kalender**: Nur kombinierter Kalender (konfigurierbar)

## 🐛 Fehlerbehebung

### Keine Action-Buttons in Benachrichtigungen?
- Prüfe ob Mobile App Benachrichtigungen unterstützt
- iOS: "Mitteilungen" in App-Einstellungen prüfen
- Android: Notification Channels aktivieren

### Verlängerung fehlgeschlagen?
- Medien sind möglicherweise noch nicht verlängerbar
- Prüfe `renewal_date` Attribut am Sensor
- Manche Medien haben Verlängerungssperren
- Verlängerungsdatum wird automatisch beim Button-Press aktualisiert

### Benachrichtigungen kommen nicht?
1. Test-Benachrichtigung senden: `service: bibkat.test_notification`
2. Benachrichtigungsdienst in Optionen prüfen
3. HA Mobile App Verbindung prüfen

### Keine Vormerkungen sichtbar?
- Vormerkungen werden aus der Familienseite gelesen
- Prüfe ob Vormerkungen auf der Webseite angezeigt werden
- Debug-Skript: `python debug_reservations.py <username> <password>`

### Doppelte Kalendereinträge?
- Ab v0.6.0 wird nur noch ein kombinierter Kalender erstellt
- Alte Kalender-Entities manuell löschen falls vorhanden

## 📝 Version History

### v0.6.0 (2025-06-19) - Reservations & Improvements
- 📚 **NEU**: Vormerkungen/Reservierungen mit eigenen Sensoren
- 🔄 Auto-Update Verlängerungsdatum bei Button-Press
- 📅 Kalender-Optimierung (keine Duplikate mehr)
- 🏷️ Externe Familienmitglieder Support
- 🔧 Verbesserte Fehlerbehandlung
- 🌍 Vollständige Übersetzungen (DE/EN)

### v0.5.0 (2025-06-18) - Individual Media Entities 
- 📚 **NEU**: Jedes Buch als eigene Entity (`button.bibkat_boehl_buchname_12345`)
- 🔘 Ein-Klick-Verlängerung durch Button-Press
- 🎯 Native Dashboards ohne Custom Cards
- 📊 Template Slot System für stabile Dashboard-IDs
- 🔄 Dynamische Gruppen via Automation
- 📱 Perfekte Mobile App Integration

### v0.3.1 (2025-06-18) - Attribute Translation
- 🌍 Automatische Übersetzung der Sensor-Attribute basierend auf HA-Sprache
- 🇩🇪 Deutsche Attribute für deutsche HA-Installationen
- 📚 Vollständige Dokumentation der Attributnamen

### v0.3.0 (2025-06-18) - Major Update
- ✨ Multi-Account Support pro Bibliothek
- 🔔 Actionable Notifications mit Smart Buttons
- 💰 Kontostand-Tracking (Gebühren, Kartenablauf)
- 📅 Erweiterte Datumsfunktionen (ISO-Format, is_renewable_now)
- 🌍 Multi-Language Support (DE/EN)
- ⚙️ Options Flow für Benachrichtigungseinstellungen
- 🎯 Notification Action Handler
- 📱 Volle Mobile App Integration

### v0.2.0
- 🏛️ Multi-Bibliothek Support
- 📅 Echte Datumsberechnung statt Platzhalter
- 🔄 Verlängerungsdatum-Anzeige
- 🏷️ Generischer Name "bibkat"

### v0.1.0
- 🚀 Initiale Version für KÖB Böhl
- 📚 Basis-Funktionen: Login, Anzeige, Verlängerung

## 👏 Credits

Entwickelt für alle BibKat-Bibliotheken.  
BibKat System von IBTC.

## 📄 Lizenz

Dieses Projekt steht unter der MIT-Lizenz.