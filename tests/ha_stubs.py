"""Minimale Platzhalter für die Home-Assistant-Module, die controller.py importiert.

Nur so viel, dass die Steuerlogik ohne installiertes Home Assistant läuft.
"""

from __future__ import annotations

import datetime as _dt
import sys
import types


def _module(name: str, **attrs) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    sys.modules[name] = module
    return module


class Platform:
    BINARY_SENSOR = "binary_sensor"
    NUMBER = "number"
    SENSOR = "sensor"
    SWITCH = "switch"


class UnitOfTemperature:
    CELSIUS = "°C"
    FAHRENHEIT = "°F"
    KELVIN = "K"


class ConfigEntry:
    def __class_getitem__(cls, item):
        return cls


class HomeAssistantError(Exception):
    def __init__(self, *args, translation_domain=None, translation_key=None, **kwargs):
        super().__init__(*args)
        self.translation_domain = translation_domain
        self.translation_key = translation_key


class ServiceValidationError(HomeAssistantError):
    pass


class TemperatureConverter:
    @staticmethod
    def convert(value: float, from_unit: str, to_unit: str) -> float:
        assert to_unit == UnitOfTemperature.CELSIUS
        if from_unit == UnitOfTemperature.FAHRENHEIT:
            return (value - 32) * 5 / 9
        if from_unit == UnitOfTemperature.KELVIN:
            return value - 273.15
        return value


class Store:
    # In Tests setzen, um gespeicherte Daten zu simulieren
    preset: dict | None = None

    def __init__(self, hass, version, key):
        self.saved = None

    async def async_load(self):
        return Store.preset

    def async_delay_save(self, data_func, delay):
        self.saved = data_func()


# Steuerbare Uhr für die Tests
class _Clock:
    now = _dt.datetime(2026, 1, 15, 12, 0, 0)


def _now() -> _dt.datetime:
    return _Clock.now


_module("homeassistant")
_module(
    "homeassistant.const",
    ATTR_ENTITY_ID="entity_id",
    ATTR_UNIT_OF_MEASUREMENT="unit_of_measurement",
    STATE_ON="on",
    STATE_OFF="off",
    Platform=Platform,
    UnitOfTemperature=UnitOfTemperature,
)
_module("homeassistant.config_entries", ConfigEntry=ConfigEntry)
_module(
    "homeassistant.core",
    CALLBACK_TYPE=object,
    Event=object,
    EventStateChangedData=object,
    HomeAssistant=object,
    callback=lambda func: func,
)
_module(
    "homeassistant.exceptions",
    HomeAssistantError=HomeAssistantError,
    ServiceValidationError=ServiceValidationError,
)
_module("homeassistant.helpers")
_module(
    "homeassistant.helpers.event",
    async_track_state_change_event=lambda hass, entities, action: (lambda: None),
    async_track_time_interval=lambda hass, action, interval: (lambda: None),
)
_module("homeassistant.helpers.storage", Store=Store)


class EntityRegistry:
    """Registry mit (domain, platform, unique_id) -> entity_id."""

    def __init__(self):
        self.entities: dict[tuple[str, str, str], str] = {}

    def async_get_entity_id(self, domain, platform, unique_id):
        return self.entities.get((domain, platform, unique_id))

    def async_remove(self, entity_id):
        self.entities = {k: v for k, v in self.entities.items() if v != entity_id}


registry = EntityRegistry()
_module("homeassistant.helpers.entity_registry", async_get=lambda hass: registry)
sys.modules["homeassistant.helpers"].entity_registry = sys.modules[
    "homeassistant.helpers.entity_registry"
]
_module("homeassistant.util")
_module(
    "homeassistant.util.dt",
    now=_now,
    parse_time=lambda value: _dt.time.fromisoformat(value),
    parse_datetime=lambda value: _dt.datetime.fromisoformat(value),
    as_local=lambda value: value,
)
_module("homeassistant.util.unit_conversion", TemperatureConverter=TemperatureConverter)

# --- Minimaler Nachbau für config_flow.py (voluptuous, selector, Flows) ------------


class _Marker(str):
    def __new__(cls, key, default=None):
        obj = super().__new__(cls, key)
        obj.default = default
        return obj


class Required(_Marker):
    pass


class Optional(_Marker):
    pass


class Schema:
    def __init__(self, schema):
        self.schema = dict(schema)

    def extend(self, other):
        return Schema({**self.schema, **(other.schema if isinstance(other, Schema) else other)})


_module("voluptuous", Schema=Schema, Required=Required, Optional=Optional)


class _Any:
    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs


_module(
    "homeassistant.helpers.selector",
    EntitySelector=_Any,
    EntitySelectorConfig=_Any,
    SelectSelector=_Any,
    SelectSelectorConfig=_Any,
    SelectSelectorMode=types.SimpleNamespace(LIST="list", DROPDOWN="dropdown"),
    NumberSelector=_Any,
    NumberSelectorConfig=_Any,
    NumberSelectorMode=types.SimpleNamespace(BOX="box"),
    BooleanSelector=_Any,
    TimeSelector=_Any,
)
sys.modules["homeassistant.helpers"].selector = sys.modules["homeassistant.helpers.selector"]


class _FlowBase:
    def async_show_form(self, *, step_id, data_schema, errors=None):
        return {"type": "form", "step_id": step_id, "schema": data_schema, "errors": errors or {}}

    def add_suggested_values_to_schema(self, schema, suggested):
        schema.suggested = dict(suggested)
        return schema


class ConfigFlow(_FlowBase):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        pass

    def async_create_entry(self, *, title, data, options=None):
        return {"type": "create_entry", "title": title, "data": data, "options": options}

    def _get_reconfigure_entry(self):
        return self.reconfigure_entry

    def async_update_reload_and_abort(self, entry, *, unique_id=None, data=None):
        return {"type": "abort", "unique_id": unique_id, "data": data}


class OptionsFlow(_FlowBase):
    def async_create_entry(self, *, data):
        return {"type": "create_entry", "data": data}


_cfg = sys.modules["homeassistant.config_entries"]
_cfg.ConfigFlow = ConfigFlow
_cfg.OptionsFlow = OptionsFlow
_cfg.ConfigFlowResult = dict
sys.modules["homeassistant.const"].CONF_NAME = "name"

clock = _Clock
