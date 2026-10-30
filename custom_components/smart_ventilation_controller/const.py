"""Konstanten des Smart ventilation controller."""

DOMAIN = "smart_ventilation_controller"

try:
    from homeassistant.const import UnitOfDensity

    UNIT_ABSOLUTE_HUMIDITY = UnitOfDensity.GRAMS_PER_CUBIC_METER
except (ImportError, AttributeError):  # Home Assistant vor Einführung von UnitOfDensity
    UNIT_ABSOLUTE_HUMIDITY = "g/m³"

# Einrichtung (entry.data)
CONF_INDOOR_TEMP = "indoor_temperature"
CONF_INDOOR_HUM = "indoor_humidity"
CONF_OUTDOOR_TEMP = "outdoor_temperature"
CONF_OUTDOOR_HUM = "outdoor_humidity"
CONF_WALL_TEMP = "wall_temperature"
CONF_FAN = "fan_entity"
CONF_ADDITIONAL_FANS = "additional_fans"
CONF_POWER_SOURCE = "power_source"
CONF_BATTERY_LEVEL = "battery_level"

POWER_GRID = "grid"
POWER_BATTERY = "battery"
POWER_SOURCES = [POWER_GRID, POWER_BATTERY]

# Ladezustand in Prozentpunkten über der Grenze, ab dem nach einer Sperre wieder gelüftet wird
BATTERY_HYSTERESIS = 5.0

# Optionen (entry.options)
CONF_MAX_RUNTIME = "max_runtime"  # Minuten, 0 = unbegrenzt
CONF_PAUSE = "pause_duration"  # Minuten
CONF_NIGHT_ENABLED = "night_enabled"
CONF_NIGHT_START = "night_start"
CONF_NIGHT_END = "night_end"
CONF_NOTIFY_ENTITIES = "notify_entities"
CONF_NOTIFY_SERVICES = "notify_services"
CONF_NOTIFY_EVENTS = "notify_events"

# Benachrichtigungs-Ereignisse
EVENT_ON = "turn_on"
EVENT_OFF = "turn_off"
EVENT_PAUSE = "pause"
EVENT_NIGHT = "night"
EVENT_CONDENSATION = "condensation"
EVENT_BATTERY = "battery_low"
EVENTS = [EVENT_ON, EVENT_OFF, EVENT_PAUSE, EVENT_NIGHT, EVENT_BATTERY, EVENT_CONDENSATION]

DEFAULT_OPTIONS = {
    CONF_MAX_RUNTIME: 60,
    CONF_PAUSE: 60,
    CONF_NIGHT_ENABLED: False,
    CONF_NIGHT_START: "00:00:00",
    CONF_NIGHT_END: "06:00:00",
    CONF_NOTIFY_ENTITIES: [],
    CONF_NOTIFY_SERVICES: [],
    CONF_NOTIFY_EVENTS: [EVENT_ON, EVENT_OFF, EVENT_PAUSE, EVENT_NIGHT, EVENT_BATTERY],
    CONF_POWER_SOURCE: POWER_GRID,
}

# Schwellwerte, im Dashboard über Number-Entitäten verstellbar
NUM_BUFFER_ON = "buffer_on"
NUM_BUFFER_OFF = "buffer_off"
NUM_DEWPOINT_MARGIN = "dewpoint_margin"
NUM_MIN_HUMIDITY = "min_humidity"
NUM_MIN_BATTERY = "min_battery"

DEFAULT_VALUES = {
    NUM_BUFFER_ON: 2.5,
    NUM_BUFFER_OFF: 1.0,
    NUM_DEWPOINT_MARGIN: 2.0,
    NUM_MIN_HUMIDITY: 55.0,
    NUM_MIN_BATTERY: 20.0,
}
