# Smart ventilation controller

Home-Assistant-Integration, die einen Lüfter nach **absoluter** Luftfeuchtigkeit (g/m³) schaltet, mit Kondensationsschutz über den Taupunkt, Maximallaufzeit mit Zwangspause und optionaler Nachtruhe.

## Installation

**HACS:** Repository als „Benutzerdefiniertes Repository“ (Typ *Integration*) hinzufügen und installieren.

**Manuell:** Den Ordner `custom_components/smart_ventilation_controller` nach `/config/custom_components/` kopieren und Home Assistant neu starten.

Danach: *Einstellungen → Geräte & Dienste → Integration hinzufügen → „Smart ventilation controller“*.

Voraussetzung: Home Assistant 2024.12 oder neuer. Das eigene Icon (`brand/icon.png`) wird ab Home Assistant 2026.3 angezeigt, ältere Versionen zeigen ein Platzhalter-Icon.

## Einrichtung

| Schritt | Inhalt |
|---|---|
| Einrichten | Name, Temperatur/Feuchte innen und außen, optional ein Wandtemperatur-Sensor, Lüfter (`switch`, `fan`, `light`, `input_boolean`) |
| Konfigurieren (Optionen) | Maximallaufzeit, Pausendauer, **Nachtruhe an/aus mit Start- und Endzeit**, Benachrichtigungsziele und -ereignisse |
| Neu konfigurieren | Sensoren oder Lüfter nachträglich tauschen |

Mehrere Räume: die Integration einfach mehrfach hinzufügen.

## Entitäten (pro Eintrag)

| Entität | Bedeutung |
|---|---|
| `sensor.…_status` | Statustext (Attribut `code` für Automationen) |
| `sensor.…_absolute_feuchte_innen` / `_aussen` | g/m³ |
| `sensor.…_feuchtedifferenz` | innen − außen, g/m³ |
| `sensor.…_taupunkt_innen` / `_aussen` | °C |
| `sensor.…_laufzeit` | aktuelle Laufzeit in Minuten |
| `sensor.…_pause_bis` | Ende der Zwangspause |
| `binary_sensor.…_luften_sinnvoll` | alle Einschaltbedingungen erfüllt |
| `binary_sensor.…_kondensationsgefahr` | Taupunkt außen ≥ Wandtemperatur − Sicherheitsabstand |
| `binary_sensor.…_nachtruhe` | Nachtruhe gerade aktiv |
| `binary_sensor.…_zwangspause` | Pause aktiv |
| `number.…_einschalt_puffer` | Standard 2,5 g/m³ |
| `number.…_ausschalt_puffer` | Standard 1,0 g/m³ |
| `number.…_taupunkt_sicherheitsabstand` | Standard 2 °C |
| `number.…_mindestfeuchte_innen` | Standard 65 % |
| `switch.…_automatik` | Steuerung an/aus (der Lüfter bleibt beim Abschalten im aktuellen Zustand) |

Schwellwerte, Automatik-Status und eine laufende Pause überstehen Neustarts.

## Logik (in dieser Reihenfolge, Auswertung bei jeder Sensoränderung und jede Minute)

1. Lüfter nicht verfügbar oder Automatik aus → nichts tun.
2. Nachtruhe aktiv → Lüfter aus, nicht einschalten.
3. Lüfter läuft ≥ Maximallaufzeit → aus und Zwangspause starten.
4. Ungültige Messwerte (nicht verfügbar, 0 % oder > 100 % Feuchte) → nichts schalten.
5. Lüfter läuft → aus, wenn Feuchte innen < Mindestfeuchte, Differenz < Ausschalt-Puffer oder Taupunkt außen ≥ Wandtemperatur.
6. Lüfter aus → ein, wenn keine Pause, Feuchte innen ≥ Mindestfeuchte, Differenz > Einschalt-Puffer und Taupunkt außen < Wandtemperatur − Sicherheitsabstand.

## Umstieg von der Automation

Alte Automation deaktivieren. `timer.lufter_keller_pause`, `input_text.luefter_keller_status` und `input_number.keller_grenzwert_luftfeuchte` werden nicht mehr gebraucht. Den Wert der Mindestfeuchte vorher notieren und in `number.…_mindestfeuchte_innen` übernehmen.
