# BibKat Bibliothek Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/Version-0.5.0-blue.svg)](https://github.com/iluebbe/bibkat_ha_integration)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Eine professionelle Home Assistant Integration für BibKat Bibliotheken mit Multi-Account-Support, automatischen Benachrichtigungen und Actionable Notifications.

## 🌟 Hauptfunktionen

- 📚 **Multi-Account Support** - Mehrere Leserkonten pro Bibliothek
- 🔔 **Actionable Notifications** - Verlängern direkt aus der Benachrichtigung
- 📅 **Kalender Integration** - Fälligkeiten im HA Kalender
- 🎯 **Button Entities** - Ein Klick zum Verlängern einzelner Bücher
- 📊 **Discovery Dashboard** - Auto-generierte Übersicht mit 30 Template-Sensoren
- 🌍 **Multi-Language** - Deutsch und Englisch

## 📦 Installation

Nach der Installation über HACS:

1. Gehe zu **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen**
2. Suche nach **"BibKat"**
3. Gib deine Bibliotheks-URL ein (z.B. `https://www.bibkat.de/boehl/`)
4. Füge dein(e) Leserkonto(en) hinzu

## 🔧 Konfiguration

### Benachrichtigungen
In den Integrationsoptionen kannst du:
- Benachrichtigungsdienst auswählen
- Schwellenwerte für Erinnerungen setzen
- Actionable Notifications aktivieren

### Dashboard & Template-Sensoren
- **Template-Sensoren erstellen**: Für erweiterte Dashboard-Funktionen
- **Dashboard erstellen**: Generiert ein vorkonfiguriertes Dashboard

## 📊 Entitäten

Die Integration erstellt:
- **Sensoren** pro Account für ausgeliehene Medien und Kontostand
- **Button Entities** für jedes einzelne Buch (Press = Verlängern)
- **Kalender** mit allen Fälligkeiten
- **Template Sensoren** für stabile Dashboard-Referenzen

## 🤖 Automatisierung

Beispiel für Auto-Verlängerung:
```yaml
automation:
  - alias: "BibKat - Auto-Verlängerung"
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
```

## 📚 Unterstützte Bibliotheken

Alle BibKat-Bibliotheken werden unterstützt:
- KÖB Böhl: `https://www.bibkat.de/boehl/`
- Kreuth: `https://www.bibkat.de/kreuth/`
- Und viele mehr...

## 🐛 Support

Bei Problemen:
1. Schaue in die [Dokumentation](https://github.com/iluebbe/bibkat_ha_integration)
2. Öffne ein [Issue](https://github.com/iluebbe/bibkat_ha_integration/issues)
3. Nutze die Test-Benachrichtigung: `service: bibkat.test_notification`

## 📝 Changelog

### v0.5.0 (2025-06-18)
- NEU: Jedes Buch als eigene Button Entity
- NEU: Discovery Dashboard mit Template-Sensoren
- Verbesserte Verlängerungsfunktion

### v0.3.0 (2025-06-18)
- Multi-Account Support
- Actionable Notifications
- Kalender Integration

---

**Made with ❤️ for Home Assistant**