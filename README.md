<p align="center">
  <img src="custom_components/smart_ventilation_controller/brand/icon@2x.png" alt="Smart ventilation controller" width="160">
</p>

<h1 align="center">Smart ventilation controller</h1>

<p align="center">
  Ventilates basements and other damp rooms only when it actually makes them drier.
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <a href="https://github.com/berwil84afk/ha-smart-ventilation/releases"><img src="https://img.shields.io/github/v/release/berwil84afk/ha-smart-ventilation" alt="Release"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.12%2B-18BCF2.svg" alt="Home Assistant 2024.12+">
</p>

<p align="center">
  <b>🇬🇧 English</b> · <a href="README.de.md">🇩🇪 Deutsch</a>
</p>

---

## Why this integration?

People with a damp basement often ventilate by gut feeling or by **relative** humidity. That easily backfires: in summer, warm outdoor air flows through the open window or the fan into the cool basement. There it cools down, its relative humidity rises, and water condenses on the cold walls. Ventilating makes the basement **wetter instead of drier**.

What matters is not relative but **absolute humidity**: how many grams of water a cubic metre of air actually contains. Ventilation only dries a room when the outdoor air holds less water than the indoor air.

**Summer example:**

| | Temperature | Relative humidity | Absolute humidity |
|---|---|---|---|
| Outdoor | 25 °C | 60 % | **13.8 g/m³** |
| Basement | 16 °C | 75 % | **10.2 g/m³** |

The outdoor relative humidity is lower, yet every cubic metre of outdoor air brings about 3.6 g of **additional** water into the basement. The dew point of the outdoor air is 16.7 °C, above the basement temperature, so condensation forms on the walls. → **Don't ventilate.**

**Winter example:**

| | Temperature | Relative humidity | Absolute humidity |
|---|---|---|---|
| Outdoor | 2 °C | 90 % | **5.0 g/m³** |
| Basement | 14 °C | 70 % | **8.4 g/m³** |

Although it looks "wet" outside, the cold air holds much less water. Every cubic metre of outdoor air carries about 3.4 g of moisture out of the basement. → **Ventilating pays off.**

The Smart ventilation controller does exactly this calculation around the clock and switches your fan automatically.

## What it does

- **Switches by absolute humidity:** The fan only runs when the indoor air holds noticeably more water than the outdoor air. Separate turn-on and turn-off thresholds (hysteresis) keep the fan from cycling on and off.
- **Prevents condensation:** If the outdoor dew point is too close to the wall temperature, the fan stays off. Without a wall sensor, the indoor temperature is used as an approximation.
- **Ventilates only when needed:** Below an adjustable minimum indoor humidity, it does not ventilate, even if the outdoor air is drier.
- **Protects fan and room:** After a maximum continuous runtime, a forced pause follows. The pause survives a Home Assistant restart.
- **Optional quiet hours:** The fan stays off during a time window of your choice, also across midnight.
- **Multiple fans:** Optionally add more fans, e.g. for supply and exhaust air. They are always switched together with the main fan.
- **Ignores bad readings:** Unavailable sensors or implausible values (e.g. 0 % humidity from weather stations) never cause wrong switching.
- **Makes the values visible:** Absolute humidity indoor and outdoor, the difference, dew points, runtime and a readable status are available as sensors with history.
- **Notifies on request:** Via notify entities (e.g. Telegram) or legacy notify services (e.g. the Companion app), selectable per event.
- **Entirely in the UI:** No YAML, no helpers, no templates. Set up as many rooms as you like, each independently.

## Requirements

- Home Assistant **2024.12** or newer
- A **temperature** and a **humidity sensor indoors**
- A **temperature** and a **humidity sensor outdoors** (e.g. a weather station)
- At least one switchable **fan**: `switch`, `fan`, `light` or `input_boolean` (e.g. an inline duct fan on a smart plug); more fans are optional
- Optional: a **wall temperature** sensor for more accurate condensation protection

## Installation

### Via HACS (recommended)

[![Open the repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=berwil84afk&repository=ha-smart-ventilation&category=integration)

Or manually in HACS:

1. In HACS, open **⋮ → Custom repositories** in the top right corner.
2. Add `https://github.com/berwil84afk/ha-smart-ventilation` with type **Integration**.
3. Download **Smart ventilation controller** and restart Home Assistant.

### Manual

1. Copy the folder `custom_components/smart_ventilation_controller` to `/config/custom_components/`.
2. Restart Home Assistant.

## Setup

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=smart_ventilation_controller)

Or: *Settings → Devices & services → Add integration → Smart ventilation controller*.

1. Enter a **name**, e.g. "Basement". It determines the entity names, e.g. `sensor.basement_status`.
2. Select the **sensors** for indoor and outdoor, optionally a wall temperature sensor.
3. Select the **fan**, and optionally more fans under "Additional fans" that are switched along with it.

Done. Control starts right away with sensible defaults.

For each additional room, simply add the integration again. Sensors and fans can be changed later via **⋮ → Reconfigure**.

## Settings

### Thresholds (directly on the dashboard)

The thresholds are entities of the device and can be changed on the dashboard at any time:

| Entity | Default | Meaning |
|---|---|---|
| Turn-on buffer | 2.5 g/m³ | How much more water the indoor air must hold for the fan to turn on |
| Turn-off buffer | 1.0 g/m³ | If the difference drops below this, the fan turns off again |
| Dew point safety margin | 2 °C | How far the outdoor dew point must stay below the wall temperature |
| Minimum indoor humidity | 55 % | No ventilation below this value |

### Options (via "Configure")

| Option | Default | Meaning |
|---|---|---|
| Maximum continuous runtime | 60 min | Forced pause afterwards; 0 = unlimited |
| Forced pause | 60 min | Minimum pause after the maximum runtime; 0 = no pause |
| Enable quiet hours | off | Turns the fan off during the chosen time window |
| Quiet hours from / until | 00:00 / 06:00 | Can span midnight, e.g. 22:00–06:00 |
| Notify entities | – | e.g. `notify.telegram_bot_…` |
| Notify services | – | e.g. `mobile_app_phone` |
| Notify on | on, off, pause, quiet hours | Also available: ventilation blocked by condensation risk |

Without a notify target, no messages are sent.

## Entities

Entity names follow the Home Assistant language (English or German). Example for an entry named "Basement" on an English installation:

| Entity | Description |
|---|---|
| `sensor.basement_status` | Status text, e.g. "🟢 Active – ventilating (diff 3.1 g/m³)"; the `code` attribute is meant for your own automations |
| `sensor.basement_absolute_humidity_indoor` | Absolute humidity indoors (g/m³) |
| `sensor.basement_absolute_humidity_outdoor` | Absolute humidity outdoors (g/m³) |
| `sensor.basement_humidity_difference` | Indoor minus outdoor (g/m³) |
| `sensor.basement_dew_point_indoor` | Indoor dew point (°C) |
| `sensor.basement_dew_point_outdoor` | Outdoor dew point (°C) |
| `sensor.basement_runtime` | Current fan runtime (min); with several fans, since the first one turned on |
| `sensor.basement_pause_until` | End of the forced pause |
| `binary_sensor.basement_ventilation_useful` | On when all conditions for ventilating are met |
| `binary_sensor.basement_condensation_risk` | On when ventilating could cause condensation |
| `binary_sensor.basement_quiet_hours` | On while quiet hours are active |
| `binary_sensor.basement_forced_pause` | On during the forced pause |
| `switch.basement_automatic_mode` | Control on/off; when switched off, the fan keeps its current state |
| `number.basement_…` | The four thresholds (see above) |

Thresholds, automatic mode and a running pause are kept across restarts.

Status texts and notification messages follow the Home Assistant language as well: German for German installations, English for all others. The `code` attribute of the status sensor is language-independent.

## How it decides

If several fans are configured, they act as a group: the group counts as "running" as soon as one fan is on, and all reachable fans are always switched together. A single unreachable fan does not block control of the others.

The integration evaluates on every sensor change and additionally once a minute, in this order:

1. **Fan unreachable** or **automatic mode off** → do nothing.
2. **Quiet hours active** → fan off, do not turn on.
3. **Maximum runtime reached** → fan off, start forced pause.
4. **Readings invalid** → do not switch.
5. **Fan running** → turn off as soon as
   - indoor humidity drops below the minimum, **or**
   - the difference drops below the turn-off buffer, **or**
   - the outdoor dew point reaches the wall temperature.
6. **Fan off** → turn on if
   - no forced pause is active, **and**
   - indoor humidity is at least the minimum, **and**
   - the difference is greater than the turn-on buffer, **and**
   - the outdoor dew point is at least the safety margin below the wall temperature.

Absolute humidity and dew point are calculated with the Magnus formula. Temperatures in °F or K are converted automatically.

## Examples

### Dashboard card

```yaml
type: entities
title: Basement ventilation
entities:
  - entity: sensor.basement_status
  - entity: switch.basement_automatic_mode
  - entity: sensor.basement_absolute_humidity_indoor
  - entity: sensor.basement_absolute_humidity_outdoor
  - entity: sensor.basement_humidity_difference
  - entity: binary_sensor.basement_condensation_risk
  - entity: sensor.basement_runtime
```

### Custom notification using the status code

To send messages to different recipients or in your own language, leave the integration's notifications empty and react to the `code` attribute of the status sensor instead:

```yaml
alias: Basement ventilation – quiet hours
triggers:
  - trigger: state
    entity_id: sensor.basement_status
    attribute: code
    to: night
actions:
  - action: notify.send_message
    target:
      entity_id: notify.telegram_family
    data:
      message: "🌙 Basement ventilation paused for quiet hours."
```

Possible codes: `running`, `off`, `pause`, `night`, `difference_low`, `min_humidity`, `condensation`, `invalid`, `disabled`, `fan_unavailable`, `error`.

## Icon

The integration's own icon is shown from Home Assistant **2026.3**, with a light variant in dark mode. Older versions show a placeholder icon; functionality is not affected.

## Issues and ideas

Please report bugs or ideas as an [issue](https://github.com/berwil84afk/ha-smart-ventilation/issues). Helpful details are the Home Assistant version and the messages from the log (*Settings → System → Logs*).

## License

Released under the [MIT License](LICENSE).
