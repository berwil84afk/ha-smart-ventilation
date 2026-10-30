"""Steuerlogik des Smart ventilation controller."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    UnitOfTemperature,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .calc import absolute_humidity, dew_point
from .texts import get_texts
from .const import (
    CONF_ADDITIONAL_FANS,
    CONF_BATTERY_LEVEL,
    CONF_FAN,
    CONF_INDOOR_HUM,
    CONF_INDOOR_TEMP,
    CONF_MAX_RUNTIME,
    CONF_NIGHT_ENABLED,
    CONF_NIGHT_END,
    CONF_NIGHT_START,
    CONF_NOTIFY_ENTITIES,
    CONF_NOTIFY_EVENTS,
    CONF_NOTIFY_SERVICES,
    CONF_OUTDOOR_HUM,
    CONF_OUTDOOR_TEMP,
    CONF_PAUSE,
    CONF_POWER_SOURCE,
    CONF_WALL_TEMP,
    DEFAULT_OPTIONS,
    BATTERY_HYSTERESIS,
    DEFAULT_VALUES,
    DOMAIN,
    EVENT_CONDENSATION,
    EVENT_NIGHT,
    EVENT_OFF,
    EVENT_ON,
    EVENT_BATTERY,
    EVENT_PAUSE,
    NUM_BUFFER_OFF,
    NUM_BUFFER_ON,
    NUM_DEWPOINT_MARGIN,
    NUM_MIN_BATTERY,
    NUM_MIN_HUMIDITY,
    POWER_BATTERY,
)

_LOGGER = logging.getLogger(__name__)

type SmartVentilationConfigEntry = ConfigEntry[SmartVentilationController]

STORAGE_VERSION = 1
EVAL_INTERVAL = timedelta(minutes=1)


@dataclass(slots=True)
class Readings:
    """Aktuelle Messwerte und daraus berechnete Größen."""

    indoor_temp: float | None
    indoor_rh: float | None
    outdoor_temp: float | None
    outdoor_rh: float | None
    wall_temp: float | None
    ah_indoor: float | None = None
    ah_outdoor: float | None = None
    dew_point_indoor: float | None = None
    dew_point_outdoor: float | None = None

    def __post_init__(self) -> None:
        if self.indoor_temp is not None and self.indoor_rh is not None:
            self.ah_indoor = absolute_humidity(self.indoor_temp, self.indoor_rh)
            self.dew_point_indoor = dew_point(self.indoor_temp, self.indoor_rh)
        if self.outdoor_temp is not None and self.outdoor_rh is not None:
            self.ah_outdoor = absolute_humidity(self.outdoor_temp, self.outdoor_rh)
            self.dew_point_outdoor = dew_point(self.outdoor_temp, self.outdoor_rh)
        # Ohne eigenen Wandsensor wird die Raumluft-Temperatur als Näherung genutzt
        if self.wall_temp is None:
            self.wall_temp = self.indoor_temp

    @property
    def valid(self) -> bool:
        return self.ah_indoor is not None and self.ah_outdoor is not None

    @property
    def difference(self) -> float | None:
        if not self.valid:
            return None
        return self.ah_indoor - self.ah_outdoor


@dataclass(slots=True)
class Decision:
    """Ergebnis einer Auswertung."""

    code: str
    status: str
    turn: bool | None = None
    event: str | None = None
    message: str | None = None
    start_pause: bool = False


class SmartVentilationController:
    """Wertet Sensoren aus und schaltet den Lüfter."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.config: dict[str, Any] = {**DEFAULT_OPTIONS, **entry.data, **entry.options}
        self.values: dict[str, float] = dict(DEFAULT_VALUES)
        self.automatic = True
        self.pause_until: datetime | None = None
        self.readings: Readings | None = None
        self.runtime: timedelta | None = None
        self.status = self._t("init")
        self.status_code = "init"
        self.ventilation_useful = False
        self.condensation_risk = False
        self.night_active = False
        self.battery_level: float | None = None
        self.battery_blocked = False
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._lock = asyncio.Lock()
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._available_fans: list[str] = []

    @property
    def uses_battery(self) -> bool:
        return self.config.get(CONF_POWER_SOURCE) == POWER_BATTERY

    @property
    def fan_entities(self) -> list[str]:
        """Hauptlüfter plus optionale weitere Lüfter, ohne Duplikate."""
        fans = [self.config[CONF_FAN], *self.config.get(CONF_ADDITIONAL_FANS, [])]
        return list(dict.fromkeys(fans))

    # --- Lebenszyklus -------------------------------------------------------

    async def async_load(self) -> None:
        """Gespeicherte Schwellwerte, Automatik-Status und Pause laden."""
        data = await self._store.async_load() or {}
        for key, value in data.get("values", {}).items():
            if key in self.values:
                self.values[key] = float(value)
        self.automatic = data.get("automatic", True)
        if (pause_until := data.get("pause_until")) is not None:
            self.pause_until = dt_util.parse_datetime(pause_until)

    @callback
    def async_start(self) -> None:
        entities = [
            entity_id
            for entity_id in (
                self.config[CONF_INDOOR_TEMP],
                self.config[CONF_INDOOR_HUM],
                self.config[CONF_OUTDOOR_TEMP],
                self.config[CONF_OUTDOOR_HUM],
                self.config.get(CONF_WALL_TEMP),
                self.config.get(CONF_BATTERY_LEVEL) if self.uses_battery else None,
                *self.fan_entities,
            )
            if entity_id
        ]
        self._unsubs.append(
            async_track_state_change_event(self.hass, entities, self._handle_state_change)
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._handle_interval, EVAL_INTERVAL)
        )
        self._request_evaluation()

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

    # --- Änderungen aus Entitäten -------------------------------------------

    async def async_set_value(self, key: str, value: float) -> None:
        self.values[key] = value
        self._save()
        await self.async_evaluate()

    async def async_set_automatic(self, enabled: bool) -> None:
        self.automatic = enabled
        self._save()
        await self.async_evaluate()

    # --- Auswertung ---------------------------------------------------------

    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        self._request_evaluation()

    @callback
    def _handle_interval(self, now: datetime) -> None:
        self._request_evaluation()

    @callback
    def _request_evaluation(self) -> None:
        self.entry.async_create_background_task(
            self.hass, self.async_evaluate(), f"{DOMAIN}_evaluate"
        )

    async def async_evaluate(self) -> None:
        async with self._lock:
            now = dt_util.now()
            self.readings = readings = self._read_sensors()

            # Alle Lüfter gelten als Gruppe: an, sobald einer läuft; geschaltet
            # werden nur die erreichbaren
            fan_states = [
                state
                for entity_id in self.fan_entities
                if (state := self.hass.states.get(entity_id)) is not None
                and state.state in (STATE_ON, STATE_OFF)
            ]
            self._available_fans = [state.entity_id for state in fan_states]
            running = [state for state in fan_states if state.state == STATE_ON]
            fan_available = bool(fan_states)
            fan_on = bool(running)
            self.runtime = now - min(state.last_changed for state in running) if running else None

            self.night_active = self._in_night_window(now.time())
            self._update_battery()
            if self.pause_until is not None and now >= self.pause_until:
                self.pause_until = None
                self._save()
            self._update_flags(readings)

            decision = self._decide(readings, fan_available, fan_on)
            previous_code = self.status_code

            if decision.start_pause:
                self.pause_until = now + timedelta(minutes=int(self.config[CONF_PAUSE]))
                self._save()

            if decision.turn is not None and not await self._async_switch_fan(decision.turn):
                decision = Decision("error", self._t("error"))

            self.status_code = decision.code
            self.status = decision.status

            # Schaltvorgänge immer melden, reine Statusmeldungen nur beim Wechsel
            if decision.message and (decision.turn is not None or decision.code != previous_code):
                await self._async_notify(decision.event, decision.message)

            for update_callback in list(self._listeners):
                update_callback()

    def _update_flags(self, r: Readings) -> None:
        if not r.valid:
            self.ventilation_useful = False
            self.condensation_risk = False
            return
        v = self.values
        self.condensation_risk = r.dew_point_outdoor >= r.wall_temp - v[NUM_DEWPOINT_MARGIN]
        self.ventilation_useful = (
            r.difference > v[NUM_BUFFER_ON]
            and r.indoor_rh >= v[NUM_MIN_HUMIDITY]
            and not self.condensation_risk
        )

    def _decide(self, r: Readings, fan_available: bool, fan_on: bool) -> Decision:
        v = self.values
        t = self._t
        title = self.entry.title

        if not fan_available:
            return Decision("fan_unavailable", t("fan_unavailable"))

        if not self.automatic:
            return Decision("disabled", t("disabled_manual" if fan_on else "disabled"))

        if self.night_active:
            end = str(self.config[CONF_NIGHT_END])[:5]
            status = t("night", end=end)
            if fan_on:
                return Decision(
                    "night",
                    status,
                    turn=False,
                    event=EVENT_NIGHT,
                    message=t("night_message", title=title, end=end),
                )
            return Decision("night", status)

        max_runtime = int(self.config[CONF_MAX_RUNTIME])
        if fan_on and max_runtime > 0 and self.runtime >= timedelta(minutes=max_runtime):
            pause = int(self.config[CONF_PAUSE])
            return Decision(
                "pause",
                t("max_runtime", max_runtime=max_runtime),
                turn=False,
                event=EVENT_PAUSE,
                message=t("max_runtime_message", title=title, max_runtime=max_runtime, pause=pause),
                start_pause=pause > 0,
            )

        if self.uses_battery:
            if self.battery_level is None:
                # Ohne gültigen Ladezustand nicht einschalten; ein laufender Lüfter
                # wird normal weitergesteuert (Maximallaufzeit greift)
                if not fan_on:
                    return Decision("battery_unknown", t("battery_unknown"))
            elif self.battery_blocked:
                min_battery = v[NUM_MIN_BATTERY]
                status = t(
                    "battery_low",
                    level=self.battery_level,
                    release=min_battery + BATTERY_HYSTERESIS,
                )
                if fan_on:
                    return Decision(
                        "battery_low",
                        status,
                        turn=False,
                        event=EVENT_BATTERY,
                        message=t(
                            "battery_low_message",
                            title=title,
                            level=self.battery_level,
                            min_battery=min_battery,
                        ),
                    )
                return Decision("battery_low", status)

        if not r.valid:
            return Decision("invalid", t("invalid_running" if fan_on else "invalid"))

        diff = r.difference
        min_rh = v[NUM_MIN_HUMIDITY]

        if fan_on:
            if r.indoor_rh < min_rh:
                reason = t("reason_min_humidity")
            elif diff < v[NUM_BUFFER_OFF]:
                reason = t("reason_buffer_off")
            elif r.dew_point_outdoor >= r.wall_temp:
                # Ausschalten erst, wenn der Sicherheitsabstand ganz aufgebraucht ist
                # (Hysterese gegenüber der Einschaltbedingung)
                reason = t("reason_condensation")
            else:
                return Decision("running", t("running", diff=diff))
            return Decision(
                "off",
                t("off", reason=reason),
                turn=False,
                event=EVENT_OFF,
                message=t("off_message", title=title, values=self._values_text(r), reason=reason),
            )

        if self.pause_until is not None:
            until = dt_util.as_local(self.pause_until)
            return Decision("pause", t("pause", until=f"{until:%H:%M}"))

        if r.indoor_rh < min_rh:
            return Decision("min_humidity", t("min_humidity", min_rh=min_rh, rh=r.indoor_rh))

        if diff <= v[NUM_BUFFER_ON]:
            return Decision("difference_low", t("difference_low", diff=diff))

        if self.condensation_risk:
            detail = t(
                "condensation_detail", dew_point=r.dew_point_outdoor, wall=r.wall_temp, diff=diff
            )
            return Decision(
                "condensation",
                t("condensation", detail=detail),
                event=EVENT_CONDENSATION,
                message=t("condensation_message", title=title, detail=detail),
            )

        return Decision(
            "running",
            t("running", diff=diff),
            turn=True,
            event=EVENT_ON,
            message=t("on_message", title=title, values=self._values_text(r)),
        )

    # --- Hilfsfunktionen ----------------------------------------------------

    def _in_night_window(self, now: time) -> bool:
        if not self.config[CONF_NIGHT_ENABLED]:
            return False
        start = dt_util.parse_time(str(self.config[CONF_NIGHT_START]))
        end = dt_util.parse_time(str(self.config[CONF_NIGHT_END]))
        if start is None or end is None or start == end:
            return False
        if start < end:
            return start <= now < end
        # Zeitfenster über Mitternacht, z. B. 22:00–06:00
        return now >= start or now < end

    def _read_sensors(self) -> Readings:
        return Readings(
            indoor_temp=self._read_temperature(self.config[CONF_INDOOR_TEMP]),
            indoor_rh=self._read_humidity(self.config[CONF_INDOOR_HUM]),
            outdoor_temp=self._read_temperature(self.config[CONF_OUTDOOR_TEMP]),
            outdoor_rh=self._read_humidity(self.config[CONF_OUTDOOR_HUM]),
            wall_temp=self._read_temperature(self.config.get(CONF_WALL_TEMP)),
        )

    def _read_float(self, entity_id: str | None) -> float | None:
        if not entity_id or (state := self.hass.states.get(entity_id)) is None:
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    def _read_temperature(self, entity_id: str | None) -> float | None:
        value = self._read_float(entity_id)
        if value is None:
            return None
        unit = self.hass.states.get(entity_id).attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit in (UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.KELVIN):
            value = TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
        return value

    def _update_battery(self) -> None:
        """Ladezustand lesen; Sperre unter der Grenze, Freigabe erst ab Grenze + Hysterese."""
        if not self.uses_battery:
            self.battery_level = None
            self.battery_blocked = False
            return
        value = self._read_float(self.config.get(CONF_BATTERY_LEVEL))
        self.battery_level = value if value is not None and 0 <= value <= 100 else None
        if self.battery_level is None:
            return
        min_battery = self.values[NUM_MIN_BATTERY]
        if self.battery_level < min_battery:
            self.battery_blocked = True
        elif self.battery_level >= min_battery + BATTERY_HYSTERESIS:
            self.battery_blocked = False

    def _read_humidity(self, entity_id: str | None) -> float | None:
        # 0 % (z. B. hp2000-Aussetzer) und unplausible Werte gelten als ungültig
        value = self._read_float(entity_id)
        return value if value is not None and 0 < value <= 100 else None

    def _t(self, key: str, **kwargs: Any) -> str:
        """Text in der aktuellen Systemsprache von Home Assistant."""
        return get_texts(self.hass.config.language)[key].format(**kwargs)

    def _values_text(self, r: Readings) -> str:
        return self._t(
            "values",
            in_t=r.indoor_temp,
            in_rh=r.indoor_rh,
            in_ah=r.ah_indoor,
            out_t=r.outdoor_temp,
            out_rh=r.outdoor_rh,
            out_ah=r.ah_outdoor,
            diff=r.difference,
            dew_point=r.dew_point_outdoor,
        )

    async def _async_switch_fan(self, turn_on: bool) -> bool:
        service = "turn_on" if turn_on else "turn_off"
        fans = self._available_fans
        try:
            await self.hass.services.async_call(
                "homeassistant", service, {ATTR_ENTITY_ID: fans}, blocking=True
            )
        except HomeAssistantError as err:
            _LOGGER.error("Could not switch fan(s) %s: %s", ", ".join(fans), err)
            return False
        return True

    async def _async_notify(self, event: str | None, message: str) -> None:
        if event not in self.config.get(CONF_NOTIFY_EVENTS, []):
            return
        if entities := self.config.get(CONF_NOTIFY_ENTITIES):
            try:
                await self.hass.services.async_call(
                    "notify",
                    "send_message",
                    {ATTR_ENTITY_ID: entities, "message": message},
                    blocking=True,
                )
            except HomeAssistantError as err:
                _LOGGER.warning("Notification failed: %s", err)
        for service in self.config.get(CONF_NOTIFY_SERVICES, []):
            service = service.removeprefix("notify.")
            try:
                await self.hass.services.async_call(
                    "notify", service, {"message": message}, blocking=True
                )
            except HomeAssistantError as err:
                _LOGGER.warning("Notification via notify.%s failed: %s", service, err)

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(self._data_to_save, 1)

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        return {
            "values": self.values,
            "automatic": self.automatic,
            "pause_until": self.pause_until.isoformat() if self.pause_until else None,
        }
