# Changelog

## [0.8.0] - 2025-01-20

### 🐛 Behoben
- **Verlängerungsfunktion repariert** - Anpassung an neue BibKat API (2025)
  - Neue API-URL: `https://www.bibkat.de/{CATALOG_CODE}/api/renew/`
  - Automatische Erkennung des Bibliotheks-Catalog-Codes (z.B. BGX570083 für Böhl)
  - Funktioniert mit ALLEN BibKat-Bibliotheken durch dynamische Code-Ermittlung
  - Zweistufiger Verlängerungsprozess: GET (Modal) → POST (Bestätigung)
  - Alte URL `/reader/renew/` funktioniert nicht mehr (404)
- **Media-ID Extraktion verbessert** - Korrekte Erkennung aus `data-id` Attributen
- **Verlängerbare Medien** - Werden jetzt korrekt als `is_renewable_now` markiert
- **NoneType Error behoben** - Coordinator prüft jetzt auf None-Werte

### 🔧 Technische Verbesserungen
- Debug-Logging für API-Aufrufe erweitert
- Fehlerbehandlung bei 404-Responses verbessert
- Page-Content wird für Catalog-Code-Extraktion gespeichert

## [0.7.0] - 2025-01-19

### ✨ Neue Features
- **Discovery Dashboard** - Auto-generiertes Dashboard mit Template-Sensoren
- **Template Sensor Auto-Creation** - 30 Slots + 90 Binary Sensoren für Dashboard
- **Config Flow Integration** - Template-Sensoren direkt aus UI erstellen
- **Dashboard-Kategorien** - Automatische Sortierung nach Fälligkeit

### 🐛 Behoben
- Template-Sensor-Fehler mit None-Werten behoben
- Support für `!include_dir_merge_list` Format
- Dashboard-Button-Bestätigungsdialoge korrigiert
- Kalender-Duplikate durch Media-ID-Tracking verhindert

## [0.6.0] - 2025-01-19

### ✨ Neue Features
- **Browser-basierte Verlängerungsdatum-Extraktion** - Primäre Methode wenn aktiviert
- **Sichere Credential-Speicherung** - Verschlüsselte Speicherung mit HA Store
- **Automatisches Session-Management** - Caching und Re-Authentifizierung
- **UI-basierte Familien-Credentials** - Nachträgliches Hinzufügen von Familienmitgliedern

### 🔧 Verbesserungen
- Authentifizierung in `BibKatAuthHelper` zentralisiert
- Session-Caching reduziert Login-Anfragen
- Saubere Trennung von Authentifizierung und API-Logik
- Reduziertes API-Logging (von 200+ auf minimale Nachrichten)

## [0.5.0] - 2025-01-18

### ✨ Neue Features
- **Vollständige Familien-Unterstützung** - Alle Familienmitglieder können verlängern
- **Dynamische Sensor-Erstellung** - Sensoren für alle Familienmitglieder
- **Einheitliches Account-Modell** - Echte Account-Nummern statt external_XXX
- **Multi-Methoden-Verlängerung** - AJAX und form-basierte Verlängerung

### 🐛 Behoben
- Familienmitglieder-Medien können über Familienseite verlängert werden
- Media-Button-Entities werden automatisch entfernt wenn zurückgegeben
- Verlängerungsdatum-Tracking über alle Instanzen eines Mediums

## Ältere Versionen

Siehe [GitHub Releases](https://github.com/iluebbe/bibkat_ha_integration/releases) für vollständige Historie.