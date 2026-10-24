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
from .const import (
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
    CONF_WALL_TEMP,
    DEFAULT_OPTIONS,
    DEFAULT_VALUES,
    DOMAIN,
    EVENT_CONDENSATION,
    EVENT_NIGHT,
    EVENT_OFF,
    EVENT_ON,
    EVENT_PAUSE,
    NUM_BUFFER_OFF,
    NUM_BUFFER_ON,
    NUM_DEWPOINT_MARGIN,
    NUM_MIN_HUMIDITY,
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
        self.status = "Initialisierung …"
        self.status_code = "init"
        self.ventilation_useful = False
        self.condensation_risk = False
        self.night_active = False
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._lock = asyncio.Lock()
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsubs: list[CALLBACK_TYPE] = []

    @property
    def fan_entity(self) -> str:
        return self.config[CONF_FAN]

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
                self.fan_entity,
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

            fan_state = self.hass.states.get(self.fan_entity)
            fan_available = fan_state is not None and fan_state.state in (STATE_ON, STATE_OFF)
            fan_on = fan_available and fan_state.state == STATE_ON
            self.runtime = now - fan_state.last_changed if fan_on else None

            self.night_active = self._in_night_window(now.time())
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
                decision = Decision("error", "❗ Fehler beim Schalten des Lüfters")

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
        title = self.entry.title

        if not fan_available:
            return Decision("fan_unavailable", "⚪ Lüfter nicht verfügbar")

        if not self.automatic:
            suffix = " – Lüfter läuft (manuell)" if fan_on else ""
            return Decision("disabled", f"⚪ Automatik deaktiviert{suffix}")

        if self.night_active:
            end = str(self.config[CONF_NIGHT_END])[:5]
            status = f"😴 Inaktiv – Nachtruhe bis {end} Uhr"
            if fan_on:
                return Decision(
                    "night",
                    status,
                    turn=False,
                    event=EVENT_NIGHT,
                    message=f"🌙 {title}: Lüfter wegen Nachtruhe ausgeschaltet (bis {end} Uhr)",
                )
            return Decision("night", status)

        max_runtime = int(self.config[CONF_MAX_RUNTIME])
        if fan_on and max_runtime > 0 and self.runtime >= timedelta(minutes=max_runtime):
            pause = int(self.config[CONF_PAUSE])
            return Decision(
                "pause",
                f"⏸️ Inaktiv – Pause nach Maximallaufzeit ({max_runtime} min)",
                turn=False,
                event=EVENT_PAUSE,
                message=(
                    f"⏸️ {title}: Lüfter nach {max_runtime} min Laufzeit pausiert "
                    f"(mind. {pause} min Pause)"
                ),
                start_pause=pause > 0,
            )

        if not r.valid:
            if fan_on:
                return Decision("invalid", "⚠️ Ungültige Sensorwerte – Lüfter läuft weiter")
            return Decision("invalid", "⚪ Inaktiv – ungültige Sensorwerte")

        diff = r.difference
        min_rh = v[NUM_MIN_HUMIDITY]

        if fan_on:
            if r.indoor_rh < min_rh:
                reason = "Mindestfeuchte unterschritten"
            elif diff < v[NUM_BUFFER_OFF]:
                reason = "AH-Puffer unterschritten"
            elif r.dew_point_outdoor >= r.wall_temp:
                # Ausschalten erst, wenn der Sicherheitsabstand ganz aufgebraucht ist
                # (Hysterese gegenüber der Einschaltbedingung)
                reason = "Kondensationsgefahr"
            else:
                return Decision("running", f"🟢 Aktiv – Lüftung läuft (Diff {diff:.1f} g/m³)")
            return Decision(
                "off",
                f"🔴 Inaktiv – {reason}",
                turn=False,
                event=EVENT_OFF,
                message=f"💨 🔴 {title}: Lüfter ausgeschaltet\n{self._values_text(r)}\nGrund: {reason}",
            )

        if self.pause_until is not None:
            until = dt_util.as_local(self.pause_until)
            return Decision("pause", f"⏸️ Inaktiv – Zwangspause bis {until:%H:%M} Uhr")

        if r.indoor_rh < min_rh:
            return Decision(
                "min_humidity",
                f"🔴 Inaktiv – Feuchte innen < {min_rh:.0f} % ({r.indoor_rh:.0f} %)",
            )

        if diff <= v[NUM_BUFFER_ON]:
            return Decision("difference_low", f"🔴 Inaktiv – AH-Differenz zu gering ({diff:.1f} g/m³)")

        if self.condensation_risk:
            text = (
                f"Taupunkt außen {r.dew_point_outdoor:.1f} °C, "
                f"Wand {r.wall_temp:.1f} °C, Diff {diff:.1f} g/m³"
            )
            return Decision(
                "condensation",
                f"⚠️ Inaktiv – Kondensationsgefahr ({text})",
                event=EVENT_CONDENSATION,
                message=f"⚠️ {title}: Lüften wäre sinnvoll, aber Kondensationsgefahr ({text})",
            )

        return Decision(
            "running",
            f"🟢 Aktiv – Lüftung läuft (Diff {diff:.1f} g/m³)",
            turn=True,
            event=EVENT_ON,
            message=f"💨 🟢 {title}: Lüfter eingeschaltet\n{self._values_text(r)}",
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

    def _read_humidity(self, entity_id: str | None) -> float | None:
        # 0 % (z. B. hp2000-Aussetzer) und unplausible Werte gelten als ungültig
        value = self._read_float(entity_id)
        return value if value is not None and 0 < value <= 100 else None

    @staticmethod
    def _values_text(r: Readings) -> str:
        return (
            f"Innen: {r.indoor_temp:.1f} °C / {r.indoor_rh:.0f} % → {r.ah_indoor:.2f} g/m³\n"
            f"Außen: {r.outdoor_temp:.1f} °C / {r.outdoor_rh:.0f} % → {r.ah_outdoor:.2f} g/m³\n"
            f"Differenz: {r.difference:.2f} g/m³\n"
            f"Taupunkt außen: {r.dew_point_outdoor:.1f} °C"
        )

    async def _async_switch_fan(self, turn_on: bool) -> bool:
        service = "turn_on" if turn_on else "turn_off"
        try:
            await self.hass.services.async_call(
                "homeassistant", service, {ATTR_ENTITY_ID: self.fan_entity}, blocking=True
            )
        except HomeAssistantError as err:
            _LOGGER.error("Lüfter %s konnte nicht geschaltet werden: %s", self.fan_entity, err)
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
                _LOGGER.warning("Benachrichtigung fehlgeschlagen: %s", err)
        for service in self.config.get(CONF_NOTIFY_SERVICES, []):
            service = service.removeprefix("notify.")
            try:
                await self.hass.services.async_call(
                    "notify", service, {"message": message}, blocking=True
                )
            except HomeAssistantError as err:
                _LOGGER.warning("Benachrichtigung über notify.%s fehlgeschlagen: %s", service, err)

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
