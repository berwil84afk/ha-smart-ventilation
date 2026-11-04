"""Tests für Formeln und Steuerlogik, ohne installiertes Home Assistant.

Aufruf im Repo-Ordner: python -m unittest discover -s tests -v
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import os
import string
import sys
import types
import unittest

import ha_stubs  # noqa: F401  (muss vor der Integration geladen werden)
from ha_stubs import HomeAssistantError, ServiceValidationError, clock

REPO = os.environ.get("REPO") or os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(REPO, "custom_components"))

from smart_ventilation_controller import calc  # noqa: E402
from smart_ventilation_controller.const import (  # noqa: E402
    CONF_ADDITIONAL_FANS,
    CONF_FAN,
    CONF_INDOOR_HUM,
    CONF_INDOOR_TEMP,
    CONF_NIGHT_ENABLED,
    CONF_NIGHT_END,
    CONF_NIGHT_START,
    CONF_NOTIFY_ENTITIES,
    CONF_NOTIFY_EVENTS,
    CONF_NOTIFY_SERVICES,
    CONF_OUTDOOR_HUM,
    CONF_OUTDOOR_TEMP,
    CONF_WALL_TEMP,
    EVENTS,
)
from smart_ventilation_controller.controller import SmartVentilationController  # noqa: E402
from smart_ventilation_controller.texts import TEXTS, get_texts  # noqa: E402

NOON = dt.datetime(2026, 1, 15, 12, 0, 0)


# --- Nachbau von hass, Zuständen und Diensten ------------------------------


@dataclass
class State:
    entity_id: str
    state: str
    attributes: dict = field(default_factory=dict)
    last_changed: dt.datetime = NOON


class States:
    def __init__(self):
        self._states: dict[str, State] = {}

    def set(self, entity_id, state, attributes=None, last_changed=None):
        self._states[entity_id] = State(
            entity_id, str(state), attributes or {}, last_changed or clock.now
        )

    def get(self, entity_id):
        return self._states.get(entity_id)


class Services:
    def __init__(self, states: States):
        self.states = states
        self.calls: list[tuple[str, str, dict]] = []
        self.fail = False

    async def async_call(self, domain, service, data, blocking=False):
        if self.fail:
            raise HomeAssistantError("Testfehler")
        self.calls.append((domain, service, data))
        if domain == "homeassistant":
            new_state = "on" if service == "turn_on" else "off"
            for entity_id in data["entity_id"]:
                self.states.set(entity_id, new_state)

    def switch_calls(self):
        return [(s, d["entity_id"]) for dom, s, d in self.calls if dom == "homeassistant"]

    def notify_calls(self):
        return [(s, d) for dom, s, d in self.calls if dom == "notify"]


class Hass:
    def __init__(self, language="de"):
        self.states = States()
        self.services = Services(self.states)
        self.config = types.SimpleNamespace(language=language)


class Entry:
    def __init__(self, data, options):
        self.data = data
        self.options = options
        self.title = "Keller"
        self.entry_id = "test"

    def async_create_background_task(self, hass, coro, name):
        coro.close()


def make_controller(hass, *, wall=False, fans=None, options=None, power=None):
    data = {
        CONF_INDOOR_TEMP: "sensor.in_t",
        CONF_INDOOR_HUM: "sensor.in_h",
        CONF_OUTDOOR_TEMP: "sensor.out_t",
        CONF_OUTDOOR_HUM: "sensor.out_h",
        CONF_FAN: "switch.fan",
    }
    if wall:
        data[CONF_WALL_TEMP] = "sensor.wall_t"
    if fans is not None:
        data[CONF_ADDITIONAL_FANS] = fans
    if power is not None:
        data["power_source"] = power
        data["battery_level"] = "sensor.battery"
    return SmartVentilationController(hass, Entry(data, options or {}))


def set_climate(hass, indoor, outdoor, wall=None):
    hass.states.set("sensor.in_t", indoor[0])
    hass.states.set("sensor.in_h", indoor[1])
    hass.states.set("sensor.out_t", outdoor[0])
    hass.states.set("sensor.out_h", outdoor[1])
    if wall is not None:
        hass.states.set("sensor.wall_t", wall)


# Typische Wetterlagen (Werte im README nachgerechnet)
WINTER = ((14, 70), (2, 90))  # innen 8,44 g/m³, außen 5,00 g/m³ → lüften
SUMMER = ((16, 75), (25, 60))  # innen 10,22 g/m³, außen 13,81 g/m³ → nicht lüften
SMALL_DIFF = ((14, 70), (10, 80))  # Differenz 0,92 g/m³ < Ausschalt-Puffer
HYSTERESIS = ((14, 70), (6, 95))  # Differenz ~1,5 g/m³, zwischen beiden Puffern


class Base(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        clock.now = NOON
        self.hass = Hass()
        self.hass.states.set("switch.fan", "off")


# --- Formeln ----------------------------------------------------------------


class CalcTests(unittest.TestCase):
    def test_absolute_humidity_reference_values(self):
        # Tabellenwerte: 20 °C / 100 % ≈ 17,3 g/m³, 20 °C / 50 % ≈ 8,6 g/m³
        self.assertAlmostEqual(calc.absolute_humidity(20, 100), 17.3, delta=0.1)
        self.assertAlmostEqual(calc.absolute_humidity(20, 50), 8.64, delta=0.01)
        self.assertAlmostEqual(calc.absolute_humidity(0, 100), 4.85, delta=0.05)

    def test_dew_point(self):
        self.assertAlmostEqual(calc.dew_point(20, 100), 20.0, delta=0.01)
        self.assertAlmostEqual(calc.dew_point(20, 50), 9.27, delta=0.05)
        self.assertAlmostEqual(calc.dew_point(25, 60), 16.69, delta=0.05)
        self.assertLess(calc.dew_point(-5, 90), -5)

    def test_readme_examples(self):
        self.assertAlmostEqual(calc.absolute_humidity(25, 60), 13.8, delta=0.05)
        self.assertAlmostEqual(calc.absolute_humidity(16, 75), 10.2, delta=0.05)
        self.assertAlmostEqual(calc.absolute_humidity(2, 90), 5.0, delta=0.05)
        self.assertAlmostEqual(calc.absolute_humidity(14, 70), 8.4, delta=0.05)


# --- Messwerte ----------------------------------------------------------------


class ReadingTests(Base):
    async def test_zero_humidity_is_invalid(self):
        set_climate(self.hass, (14, 70), (2, 0))
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertFalse(c.readings.valid)
        self.assertEqual(c.status_code, "invalid")
        self.assertEqual(self.hass.services.switch_calls(), [])

    async def test_unavailable_sensor_is_invalid(self):
        set_climate(self.hass, (14, "unavailable"), (2, 90))
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(c.status_code, "invalid")

    async def test_fahrenheit_is_converted(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("sensor.in_t", 57.2, {"unit_of_measurement": "°F"})
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertAlmostEqual(c.readings.indoor_temp, 14.0, places=5)
        self.assertEqual(c.status_code, "running")


# --- Schaltlogik ------------------------------------------------------------


class SwitchingTests(Base):
    async def test_winter_turns_fan_on(self):
        set_climate(self.hass, *WINTER)
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [("turn_on", ["switch.fan"])])
        self.assertEqual(c.status_code, "running")
        self.assertTrue(c.ventilation_useful)

    async def test_summer_keeps_fan_off(self):
        set_climate(self.hass, *SUMMER)
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [])
        self.assertEqual(c.status_code, "difference_low")
        self.assertFalse(c.ventilation_useful)

    async def test_min_humidity_blocks(self):
        set_climate(self.hass, (16, 50), (2, 90))
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(c.status_code, "min_humidity")
        self.assertEqual(self.hass.services.switch_calls(), [])

    async def test_condensation_blocks_with_wall_sensor(self):
        # Taupunkt außen 6,7 °C ≥ Wand 8 °C − 2 °C
        set_climate(self.hass, (16, 80), (12, 70), wall=8)
        c = make_controller(self.hass, wall=True)
        await c.async_evaluate()
        self.assertTrue(c.condensation_risk)
        self.assertEqual(c.status_code, "condensation")
        self.assertEqual(self.hass.services.switch_calls(), [])

    async def test_running_fan_turns_off_below_off_buffer(self):
        set_climate(self.hass, *SMALL_DIFF)
        self.hass.states.set("switch.fan", "on")
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [("turn_off", ["switch.fan"])])
        self.assertEqual(c.status, "🔴 Inaktiv – AH-Puffer unterschritten")

    async def test_hysteresis_keeps_running_fan_on(self):
        set_climate(self.hass, *HYSTERESIS)
        self.hass.states.set("switch.fan", "on")
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [])
        self.assertEqual(c.status_code, "running")

    async def test_hysteresis_does_not_start_stopped_fan(self):
        set_climate(self.hass, *HYSTERESIS)
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [])
        self.assertEqual(c.status_code, "difference_low")

    async def test_running_fan_turns_off_below_min_humidity(self):
        set_climate(self.hass, (16, 50), (2, 90))
        self.hass.states.set("switch.fan", "on")
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [("turn_off", ["switch.fan"])])
        self.assertEqual(c.status, "🔴 Inaktiv – Ausschalt-Feuchte unterschritten")

    async def test_automatic_off_does_nothing(self):
        set_climate(self.hass, *WINTER)
        c = make_controller(self.hass)
        c.automatic = False
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [])
        self.assertEqual(c.status_code, "disabled")

    async def test_unavailable_fan(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan", "unavailable")
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(c.status_code, "fan_unavailable")
        self.assertEqual(self.hass.services.switch_calls(), [])

    async def test_switch_error_sets_error_status(self):
        set_climate(self.hass, *WINTER)
        self.hass.services.fail = True
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(c.status_code, "error")


# --- Maximallaufzeit und Pause -----------------------------------------------


class PauseTests(Base):
    async def test_max_runtime_starts_pause_and_resumes(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan", "on", last_changed=NOON - dt.timedelta(minutes=61))
        c = make_controller(self.hass)

        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [("turn_off", ["switch.fan"])])
        self.assertEqual(c.pause_until, NOON + dt.timedelta(minutes=60))
        self.assertEqual(c._store.saved["pause_until"], c.pause_until.isoformat())

        clock.now = NOON + dt.timedelta(minutes=30)
        await c.async_evaluate()
        self.assertEqual(c.status_code, "pause")
        self.assertEqual(len(self.hass.services.switch_calls()), 1)

        clock.now = NOON + dt.timedelta(minutes=61)
        await c.async_evaluate()
        self.assertIsNone(c.pause_until)
        self.assertEqual(self.hass.services.switch_calls()[-1], ("turn_on", ["switch.fan"]))

    async def test_runtime_below_limit_keeps_running(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan", "on", last_changed=NOON - dt.timedelta(minutes=59))
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [])
        self.assertEqual(c.runtime, dt.timedelta(minutes=59))

    async def test_max_runtime_zero_means_unlimited(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan", "on", last_changed=NOON - dt.timedelta(hours=5))
        c = make_controller(self.hass, options={"max_runtime": 0})
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [])


# --- Nachtruhe ----------------------------------------------------------------


class NightTests(Base):
    def night(self, start, end, enabled=True):
        return make_controller(
            self.hass,
            options={CONF_NIGHT_ENABLED: enabled, CONF_NIGHT_START: start, CONF_NIGHT_END: end},
        )

    def test_window_over_midnight(self):
        c = self.night("22:00:00", "06:00:00")
        self.assertTrue(c._in_night_window(dt.time(23, 0)))
        self.assertTrue(c._in_night_window(dt.time(5, 59)))
        self.assertFalse(c._in_night_window(dt.time(6, 0)))
        self.assertFalse(c._in_night_window(dt.time(12, 0)))
        self.assertTrue(c._in_night_window(dt.time(22, 0)))

    def test_window_same_day(self):
        c = self.night("00:00:00", "06:00:00")
        self.assertTrue(c._in_night_window(dt.time(0, 0)))
        self.assertTrue(c._in_night_window(dt.time(5, 59)))
        self.assertFalse(c._in_night_window(dt.time(6, 0)))
        self.assertFalse(c._in_night_window(dt.time(23, 59)))

    def test_disabled_or_empty_window(self):
        self.assertFalse(self.night("22:00:00", "06:00:00", enabled=False)._in_night_window(dt.time(23, 0)))
        self.assertFalse(self.night("22:00:00", "22:00:00")._in_night_window(dt.time(22, 0)))

    def test_disabled_by_default(self):
        self.assertFalse(make_controller(self.hass)._in_night_window(dt.time(3, 0)))

    async def test_night_turns_running_fan_off_and_blocks_start(self):
        set_climate(self.hass, *WINTER)
        clock.now = dt.datetime(2026, 1, 15, 23, 0)
        self.hass.states.set("switch.fan", "on")
        c = self.night("22:00:00", "06:00:00")
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [("turn_off", ["switch.fan"])])
        self.assertEqual(c.status, "😴 Inaktiv – Nachtruhe bis 06:00 Uhr")

        await c.async_evaluate()
        self.assertEqual(len(self.hass.services.switch_calls()), 1)
        self.assertTrue(c.night_active)


# --- Mehrere Lüfter -----------------------------------------------------------


class MultiFanTests(Base):
    def setUp(self):
        super().setUp()
        self.hass.states.set("switch.fan2", "off")

    async def test_all_fans_switched_together(self):
        set_climate(self.hass, *WINTER)
        c = make_controller(self.hass, fans=["switch.fan2"])
        await c.async_evaluate()
        self.assertEqual(
            self.hass.services.switch_calls(), [("turn_on", ["switch.fan", "switch.fan2"])]
        )

    async def test_duplicate_main_fan_is_ignored(self):
        c = make_controller(self.hass, fans=["switch.fan", "switch.fan2", "switch.fan2"])
        self.assertEqual(c.fan_entities, ["switch.fan", "switch.fan2"])

    async def test_unavailable_fan_is_skipped(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan3", "unavailable")
        c = make_controller(self.hass, fans=["switch.fan2", "switch.fan3", "switch.missing"])
        await c.async_evaluate()
        self.assertEqual(
            self.hass.services.switch_calls(), [("turn_on", ["switch.fan", "switch.fan2"])]
        )

    async def test_main_fan_unavailable_others_still_controlled(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan", "unavailable")
        c = make_controller(self.hass, fans=["switch.fan2"])
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [("turn_on", ["switch.fan2"])])

    async def test_all_unavailable(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan", "unavailable")
        self.hass.states.set("switch.fan2", "unavailable")
        c = make_controller(self.hass, fans=["switch.fan2"])
        await c.async_evaluate()
        self.assertEqual(c.status_code, "fan_unavailable")

    async def test_one_running_fan_counts_as_running(self):
        # Nur der zweite Lüfter läuft (z. B. manuell), seit 61 min → Maximallaufzeit
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan2", "on", last_changed=NOON - dt.timedelta(minutes=61))
        c = make_controller(self.hass, fans=["switch.fan2"])
        await c.async_evaluate()
        self.assertEqual(
            self.hass.services.switch_calls(), [("turn_off", ["switch.fan", "switch.fan2"])]
        )
        self.assertIsNotNone(c.pause_until)

    async def test_runtime_from_earliest_fan(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan", "on", last_changed=NOON - dt.timedelta(minutes=10))
        self.hass.states.set("switch.fan2", "on", last_changed=NOON - dt.timedelta(minutes=40))
        c = make_controller(self.hass, fans=["switch.fan2"])
        await c.async_evaluate()
        self.assertEqual(c.runtime, dt.timedelta(minutes=40))

    async def test_existing_entry_without_option(self):
        c = make_controller(self.hass)
        self.assertEqual(c.fan_entities, ["switch.fan"])


# --- Benachrichtigungen -------------------------------------------------------


class NotifyTests(Base):
    async def test_no_targets_no_messages(self):
        set_climate(self.hass, *WINTER)
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(self.hass.services.notify_calls(), [])

    async def test_turn_on_message(self):
        set_climate(self.hass, *WINTER)
        c = make_controller(
            self.hass,
            options={CONF_NOTIFY_ENTITIES: ["notify.tg"], CONF_NOTIFY_SERVICES: ["notify.mobile_app_x"]},
        )
        await c.async_evaluate()
        calls = self.hass.services.notify_calls()
        self.assertEqual([s for s, _ in calls], ["send_message", "mobile_app_x"])
        message = calls[0][1]["message"]
        self.assertIn("Lüfter eingeschaltet", message)
        self.assertIn("14.0 °C / 70.0 %", message)
        self.assertIn("2.0 °C / 90.0 %", message)

    async def test_event_not_selected(self):
        set_climate(self.hass, *WINTER)
        c = make_controller(
            self.hass, options={CONF_NOTIFY_ENTITIES: ["notify.tg"], CONF_NOTIFY_EVENTS: ["turn_off"]}
        )
        await c.async_evaluate()
        self.assertEqual(self.hass.services.notify_calls(), [])

    async def test_condensation_notified_once(self):
        set_climate(self.hass, (16, 80), (12, 70), wall=8)
        c = make_controller(
            self.hass,
            wall=True,
            options={CONF_NOTIFY_ENTITIES: ["notify.tg"], CONF_NOTIFY_EVENTS: list(EVENTS)},
        )
        await c.async_evaluate()
        await c.async_evaluate()
        await c.async_evaluate()
        self.assertEqual(len(self.hass.services.notify_calls()), 1)


# --- Statustexte ----------------------------------------------------------------


class StatusTextTests(Base):
    async def test_min_humidity_text_has_one_decimal(self):
        set_climate(self.hass, (16, 50.34), (2, 90))
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(c.status, "🔴 Inaktiv – Feuchte innen < 55 % (50.3 %)")

    async def test_default_values(self):
        c = make_controller(self.hass)
        self.assertEqual(c.values["min_humidity"], 55.0)
        self.assertEqual(c.values["buffer_on"], 2.5)
        self.assertEqual(c.values["buffer_off"], 1.0)


# --- Hysterese der relativen Feuchte innen ----------------------------------------


class HumidityHysteresisTests(Base):
    """Einschalt-Feuchte 65 %, Ausschalt-Feuchte 60 %; außen trocken (2 °C / 90 %)."""

    def setUp(self):
        super().setUp()
        ha_stubs.Store.preset = None

    async def controller(self, on=65, off=60):
        c = make_controller(self.hass)
        await c.async_set_value("min_humidity", on)
        await c.async_set_value("min_humidity_off", off)
        self.hass.services.calls.clear()
        return c

    async def evaluate(self, c, indoor_rh, fan="off", indoor_temp=16):
        set_climate(self.hass, (indoor_temp, indoor_rh), (2, 90))
        self.hass.states.set("switch.fan", fan)
        await c.async_evaluate()
        return self.hass.services.switch_calls()

    async def test_off_fan_starts_only_at_turn_on_humidity(self):
        c = await self.controller()
        self.assertEqual(await self.evaluate(c, 64), [])
        self.assertEqual(c.status, "🔴 Inaktiv – Feuchte innen < 65 % (64.0 %)")
        self.assertEqual(await self.evaluate(c, 65), [("turn_on", ["switch.fan"])])

    async def test_running_fan_keeps_running_between_thresholds(self):
        c = await self.controller()
        self.assertEqual(await self.evaluate(c, 62, fan="on"), [])
        self.assertEqual(c.status_code, "running")
        self.assertEqual(await self.evaluate(c, 60, fan="on"), [])

    async def test_running_fan_stops_below_turn_off_humidity(self):
        c = await self.controller()
        self.assertEqual(await self.evaluate(c, 59.9, fan="on"), [("turn_off", ["switch.fan"])])
        self.assertEqual(c.status, "🔴 Inaktiv – Ausschalt-Feuchte unterschritten")

    async def test_ventilation_useful_uses_turn_on_humidity(self):
        c = await self.controller()
        await self.evaluate(c, 62, fan="on")
        self.assertFalse(c.ventilation_useful)
        await self.evaluate(c, 66, fan="on")
        self.assertTrue(c.ventilation_useful)

    async def test_new_install_off_equals_on(self):
        c = make_controller(self.hass)
        await c.async_load()
        self.assertEqual(c.values["min_humidity"], 55.0)
        self.assertEqual(c.values["min_humidity_off"], 55.0)

    async def test_existing_install_off_follows_stored_on_value(self):
        ha_stubs.Store.preset = {"values": {"min_humidity": 65.0}}
        try:
            c = make_controller(self.hass)
            await c.async_load()
        finally:
            ha_stubs.Store.preset = None
        self.assertEqual(c.values["min_humidity"], 65.0)
        self.assertEqual(c.values["min_humidity_off"], 65.0)

    async def test_stored_off_value_is_kept(self):
        ha_stubs.Store.preset = {"values": {"min_humidity": 65.0, "min_humidity_off": 60.0}}
        try:
            c = make_controller(self.hass)
            await c.async_load()
        finally:
            ha_stubs.Store.preset = None
        self.assertEqual(c.values["min_humidity_off"], 60.0)

    async def test_same_values_behave_like_before(self):
        c = await self.controller(on=55, off=55)
        # 20 °C, damit die Differenz zur Außenluft sicher über dem Einschalt-Puffer liegt
        self.assertEqual(
            await self.evaluate(c, 54.9, fan="on", indoor_temp=20), [("turn_off", ["switch.fan"])]
        )
        self.hass.services.calls.clear()
        self.assertEqual(await self.evaluate(c, 55, indoor_temp=20), [("turn_on", ["switch.fan"])])

    async def test_off_above_on_is_rejected(self):
        c = await self.controller()
        with self.assertRaises(ServiceValidationError) as ctx:
            await c.async_set_value("min_humidity_off", 70)
        self.assertEqual(ctx.exception.translation_key, "humidity_order")
        with self.assertRaises(ServiceValidationError):
            await c.async_set_value("min_humidity", 55)
        self.assertEqual((c.values["min_humidity"], c.values["min_humidity_off"]), (65, 60))

    async def test_buffer_order_still_checked(self):
        c = make_controller(self.hass)
        with self.assertRaises(ServiceValidationError) as ctx:
            await c.async_set_value("buffer_off", 3.0)
        self.assertEqual(ctx.exception.translation_key, "buffer_order")
        await c.async_set_value("buffer_off", 2.5)
        self.assertEqual(c.values["buffer_off"], 2.5)

    async def test_english_reason(self):
        self.hass.config.language = "en"
        c = await self.controller()
        await self.evaluate(c, 59, fan="on")
        self.assertEqual(c.status, "🔴 Inactive – below turn-off humidity")


# --- Stromquelle Batterie -------------------------------------------------------


class BatteryTests(Base):
    def setUp(self):
        super().setUp()
        set_climate(self.hass, *WINTER)

    def battery(self, level):
        self.hass.states.set("sensor.battery", level)

    async def test_grid_ignores_battery_sensor(self):
        self.battery(5)
        c = make_controller(self.hass, power="grid")
        await c.async_evaluate()
        self.assertFalse(c.uses_battery)
        self.assertIsNone(c.battery_level)
        self.assertEqual(self.hass.services.switch_calls(), [("turn_on", ["switch.fan"])])

    async def test_power_source_from_options(self):
        self.battery(10)
        c = SmartVentilationController(
            self.hass,
            Entry(
                {CONF_INDOOR_TEMP: "sensor.in_t", CONF_INDOOR_HUM: "sensor.in_h",
                 CONF_OUTDOOR_TEMP: "sensor.out_t", CONF_OUTDOOR_HUM: "sensor.out_h",
                 CONF_FAN: "switch.fan"},
                {"power_source": "battery", "battery_level": "sensor.battery"},
            ),
        )
        await c.async_evaluate()
        self.assertTrue(c.uses_battery)
        self.assertEqual(c.status_code, "battery_low")

    async def test_options_override_power_source_from_old_data(self):
        self.battery(10)
        c = make_controller(self.hass, power="battery", options={"power_source": "grid"})
        await c.async_evaluate()
        self.assertFalse(c.uses_battery)
        self.assertEqual(c.status_code, "running")

    async def test_existing_entry_is_grid(self):
        self.battery(5)
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertFalse(c.uses_battery)
        self.assertEqual(c.status_code, "running")

    async def test_enough_charge_normal_logic(self):
        self.battery(80)
        c = make_controller(self.hass, power="battery")
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [("turn_on", ["switch.fan"])])
        self.assertFalse(c.battery_blocked)

    async def test_low_charge_blocks_start(self):
        self.battery(10)
        c = make_controller(self.hass, power="battery")
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [])
        self.assertEqual(c.status_code, "battery_low")
        self.assertTrue(c.battery_blocked)
        self.assertEqual(c.status, "🔋 Inaktiv – Ladezustand zu niedrig (10 %, Freigabe ab 25 %)")

    async def test_low_charge_turns_running_fan_off_and_notifies(self):
        self.battery(19)
        self.hass.states.set("switch.fan", "on")
        c = make_controller(self.hass, power="battery", options={CONF_NOTIFY_ENTITIES: ["notify.tg"]})
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [("turn_off", ["switch.fan"])])
        message = self.hass.services.notify_calls()[0][1]["message"]
        self.assertEqual(
            message, "🔋 Keller: Lüfter wegen niedrigem Ladezustand ausgeschaltet (19 %, Grenze 20 %)"
        )

    async def test_hysteresis(self):
        c = make_controller(self.hass, power="battery")
        self.battery(15)
        await c.async_evaluate()
        self.assertEqual(c.status_code, "battery_low")

        self.battery(24)
        await c.async_evaluate()
        self.assertEqual(c.status_code, "battery_low")
        self.assertEqual(self.hass.services.switch_calls(), [])

        self.battery(25)
        await c.async_evaluate()
        self.assertFalse(c.battery_blocked)
        self.assertEqual(self.hass.services.switch_calls(), [("turn_on", ["switch.fan"])])

    async def test_between_limits_without_previous_block_allows_start(self):
        # z. B. nach einem Neustart: Sperre wird nicht gespeichert
        self.battery(22)
        c = make_controller(self.hass, power="battery")
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [("turn_on", ["switch.fan"])])

    async def test_running_fan_between_limits_after_block_is_turned_off(self):
        c = make_controller(self.hass, power="battery")
        self.battery(15)
        await c.async_evaluate()
        self.battery(22)
        self.hass.states.set("switch.fan", "on")  # manuell eingeschaltet
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [("turn_off", ["switch.fan"])])

    async def test_unknown_level_blocks_start(self):
        for value in ("unavailable", 150, -1):
            with self.subTest(value=value):
                self.battery(value)
                c = make_controller(self.hass, power="battery")
                await c.async_evaluate()
                self.assertIsNone(c.battery_level)
                self.assertEqual(c.status_code, "battery_unknown")
                self.assertEqual(c.status, "🔋 Inaktiv – Ladezustand unbekannt")
        self.assertEqual(self.hass.services.switch_calls(), [])

    async def test_missing_sensor_state_blocks_start(self):
        c = make_controller(self.hass, power="battery")
        await c.async_evaluate()
        self.assertEqual(c.status_code, "battery_unknown")

    async def test_unknown_level_keeps_running_fan(self):
        self.battery("unavailable")
        self.hass.states.set("switch.fan", "on")
        c = make_controller(self.hass, power="battery")
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [])
        self.assertEqual(c.status_code, "running")

    async def test_unknown_level_running_fan_still_hits_max_runtime(self):
        self.battery("unavailable")
        self.hass.states.set("switch.fan", "on", last_changed=NOON - dt.timedelta(minutes=61))
        c = make_controller(self.hass, power="battery")
        await c.async_evaluate()
        self.assertEqual(self.hass.services.switch_calls(), [("turn_off", ["switch.fan"])])
        self.assertEqual(c.status_code, "pause")

    async def test_changing_limit_releases_block(self):
        c = make_controller(self.hass, power="battery")
        self.battery(22)
        await c.async_set_value("min_battery", 25)
        self.assertTrue(c.battery_blocked)
        self.assertEqual(self.hass.services.switch_calls(), [])

        await c.async_set_value("min_battery", 15)
        self.assertFalse(c.battery_blocked)
        self.assertEqual(self.hass.services.switch_calls(), [("turn_on", ["switch.fan"])])

    async def test_default_limit_and_event(self):
        c = make_controller(self.hass, power="battery")
        self.assertEqual(c.values["min_battery"], 20.0)
        self.assertIn("battery_low", c.config[CONF_NOTIFY_EVENTS])

    def test_switching_to_grid_removes_battery_entities(self):
        from ha_stubs import registry
        from smart_ventilation_controller import _remove_battery_entities

        entry = Entry({}, {})
        registry.entities = {
            ("number", "smart_ventilation_controller", "test_min_battery"): "number.keller_mindest_ladezustand",
            ("binary_sensor", "smart_ventilation_controller", "test_battery_low"): "binary_sensor.keller_ladezustand_zu_niedrig",
            ("number", "smart_ventilation_controller", "test_min_humidity"): "number.keller_mindestfeuchte_innen",
            ("number", "smart_ventilation_controller", "other_min_battery"): "number.anderer_eintrag",
        }
        _remove_battery_entities(self.hass, entry)
        self.assertEqual(
            sorted(registry.entities.values()),
            ["number.anderer_eintrag", "number.keller_mindestfeuchte_innen"],
        )

    async def test_english_texts(self):
        self.hass.config.language = "en"
        self.battery(10)
        c = make_controller(self.hass, power="battery")
        await c.async_evaluate()
        self.assertEqual(c.status, "🔋 Inactive – battery level too low (10 %, resumes at 25 %)")
        self.battery("unknown")
        await c.async_evaluate()
        self.assertEqual(c.status, "🔋 Inactive – battery level unknown")


# --- Sprachen -------------------------------------------------------------------


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


class TextTableTests(unittest.TestCase):
    def test_same_keys_and_placeholders(self):
        self.assertEqual(TEXTS["de"].keys(), TEXTS["en"].keys())
        for key in TEXTS["de"]:
            self.assertEqual(
                _placeholders(TEXTS["de"][key]), _placeholders(TEXTS["en"][key]), key
            )

    def test_language_selection(self):
        self.assertIs(get_texts("de"), TEXTS["de"])
        self.assertIs(get_texts("de-CH"), TEXTS["de"])
        self.assertIs(get_texts("en-GB"), TEXTS["en"])
        self.assertIs(get_texts("fr"), TEXTS["en"])
        self.assertIs(get_texts(None), TEXTS["en"])


class EnglishTests(Base):
    def setUp(self):
        super().setUp()
        self.hass.config.language = "en"

    async def test_initial_status(self):
        self.assertEqual(make_controller(self.hass).status, "Initializing …")

    async def test_turn_on_status_and_message(self):
        set_climate(self.hass, *WINTER)
        c = make_controller(self.hass, options={CONF_NOTIFY_ENTITIES: ["notify.tg"]})
        await c.async_evaluate()
        self.assertEqual(c.status, "🟢 Active – ventilating (diff 3.4 g/m³)")
        message = self.hass.services.notify_calls()[0][1]["message"]
        self.assertTrue(message.startswith("💨 🟢 Keller: fan turned on\n"))
        self.assertIn("Indoor: 14.0 °C / 70.0 % → 8.44 g/m³", message)
        self.assertIn("Outdoor dew point: 0.5 °C", message)

    async def test_turn_off_reason(self):
        set_climate(self.hass, *SMALL_DIFF)
        self.hass.states.set("switch.fan", "on")
        c = make_controller(self.hass, options={CONF_NOTIFY_ENTITIES: ["notify.tg"]})
        await c.async_evaluate()
        self.assertEqual(c.status, "🔴 Inactive – below turn-off buffer")
        self.assertIn("Reason: below turn-off buffer", self.hass.services.notify_calls()[0][1]["message"])

    async def test_quiet_hours(self):
        set_climate(self.hass, *WINTER)
        clock.now = dt.datetime(2026, 1, 15, 23, 0)
        c = make_controller(
            self.hass,
            options={CONF_NIGHT_ENABLED: True, CONF_NIGHT_START: "22:00:00", CONF_NIGHT_END: "06:00:00"},
        )
        await c.async_evaluate()
        self.assertEqual(c.status, "😴 Inactive – quiet hours until 06:00")

    async def test_min_humidity_and_difference(self):
        set_climate(self.hass, (16, 50.34), (2, 90))
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(c.status, "🔴 Inactive – indoor humidity < 55 % (50.3 %)")

        set_climate(self.hass, *SUMMER)
        await c.async_evaluate()
        self.assertTrue(c.status.startswith("🔴 Inactive – humidity difference too small ("))

    async def test_condensation(self):
        set_climate(self.hass, (16, 80), (12, 70), wall=8)
        c = make_controller(self.hass, wall=True)
        await c.async_evaluate()
        self.assertEqual(
            c.status,
            "⚠️ Inactive – condensation risk (outdoor dew point 6.7 °C, wall 8.0 °C, diff 3.4 g/m³)",
        )

    async def test_pause_and_error(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan", "on", last_changed=NOON - dt.timedelta(minutes=61))
        c = make_controller(self.hass)
        await c.async_evaluate()
        self.assertEqual(c.status, "⏸️ Inactive – pause after maximum runtime (60 min)")
        clock.now = NOON + dt.timedelta(minutes=5)
        await c.async_evaluate()
        self.assertEqual(c.status, "⏸️ Inactive – forced pause until 13:00")

        self.hass.services.fail = True
        clock.now = NOON + dt.timedelta(minutes=61)
        await c.async_evaluate()
        self.assertEqual(c.status, "❗ Error switching the fan")


class GermanTextTests(Base):
    async def test_initial_status(self):
        self.assertEqual(make_controller(self.hass).status, "Initialisierung …")

    async def test_turn_on_status_and_message(self):
        set_climate(self.hass, *WINTER)
        c = make_controller(self.hass, options={CONF_NOTIFY_ENTITIES: ["notify.tg"]})
        await c.async_evaluate()
        self.assertEqual(c.status, "🟢 Aktiv – Lüftung läuft (Diff 3.4 g/m³)")
        message = self.hass.services.notify_calls()[0][1]["message"]
        self.assertTrue(message.startswith("💨 🟢 Keller: Lüfter eingeschaltet\n"))
        self.assertIn("Innen: 14.0 °C / 70.0 % → 8.44 g/m³", message)
        self.assertIn("Taupunkt außen: 0.5 °C", message)

    async def test_pause_until(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan", "on", last_changed=NOON - dt.timedelta(minutes=61))
        c = make_controller(self.hass)
        await c.async_evaluate()
        clock.now = NOON + dt.timedelta(minutes=5)
        await c.async_evaluate()
        self.assertEqual(c.status, "⏸️ Inaktiv – Zwangspause bis 13:00 Uhr")


if __name__ == "__main__":
    unittest.main()
