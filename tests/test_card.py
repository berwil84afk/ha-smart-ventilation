"""Tests für die Dashboard-Karte: Kartendaten am Status-Sensor und Anmeldung im Frontend."""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import types
import unittest

import ha_stubs  # noqa: F401
from ha_stubs import clock, frontend_calls

REPO = os.environ.get("REPO") or os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(REPO, "custom_components"))

import smart_ventilation_controller as integration  # noqa: E402
from test_controller import NOON, WINTER, Base, make_controller, set_climate  # noqa: E402

COMPONENT = os.path.join(REPO, "custom_components", "smart_ventilation_controller")


class CardAttributeTests(Base):
    async def test_values_after_evaluation(self):
        set_climate(self.hass, *WINTER)
        c = make_controller(self.hass)
        await c.async_evaluate()
        a = c.card_attributes()
        self.assertEqual(a["code"], "running")
        self.assertEqual(a["indoor_temperature"], 14.0)
        self.assertEqual(a["indoor_humidity"], 70.0)
        self.assertEqual(a["outdoor_temperature"], 2.0)
        self.assertEqual(a["outdoor_humidity"], 90.0)
        self.assertAlmostEqual(a["absolute_humidity_indoor"], 8.44, places=2)
        self.assertAlmostEqual(a["absolute_humidity_outdoor"], 5.0, delta=0.01)
        self.assertAlmostEqual(a["difference"], 3.44, delta=0.01)
        self.assertEqual(a["buffer_on"], 2.5)
        self.assertEqual(a["buffer_off"], 1.0)
        self.assertTrue(a["automatic"])
        # Der Lüfter wurde in dieser Auswertung erst eingeschaltet
        self.assertFalse(a["fan_on"])

    async def test_fan_state_and_runtime(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan", "on", last_changed=NOON - dt.timedelta(minutes=12))
        c = make_controller(self.hass)
        await c.async_evaluate()
        a = c.card_attributes()
        self.assertTrue(a["fan_on"])
        self.assertEqual(a["runtime_minutes"], 12)

    async def test_without_readings(self):
        a = make_controller(self.hass).card_attributes()
        self.assertIsNone(a["indoor_temperature"])
        self.assertIsNone(a["difference"])
        self.assertEqual(a["runtime_minutes"], 0)
        self.assertIsNone(a["pause_until"])

    async def test_quiet_hours_and_pause(self):
        set_climate(self.hass, *WINTER)
        self.hass.states.set("switch.fan", "on", last_changed=NOON - dt.timedelta(minutes=61))
        c = make_controller(
            self.hass,
            options={"night_enabled": True, "night_start": "22:00:00", "night_end": "06:00:00"},
        )
        await c.async_evaluate()
        a = c.card_attributes()
        self.assertTrue(a["night_enabled"])
        self.assertEqual((a["night_start"], a["night_end"]), ("22:00", "06:00"))
        self.assertFalse(a["night_active"])
        self.assertEqual(a["pause_until"], (NOON + dt.timedelta(minutes=60)).isoformat())

    async def test_source_entities_for_history(self):
        a = make_controller(self.hass).card_attributes()
        self.assertEqual(a["indoor_temperature_entity"], "sensor.in_t")
        self.assertEqual(a["indoor_humidity_entity"], "sensor.in_h")
        self.assertEqual(a["outdoor_temperature_entity"], "sensor.out_t")
        self.assertEqual(a["outdoor_humidity_entity"], "sensor.out_h")

    async def test_attributes_are_json_serialisable(self):
        set_climate(self.hass, *WINTER)
        c = make_controller(self.hass)
        await c.async_evaluate()
        json.dumps(c.card_attributes())


class RestoreDefaultsTests(Base):
    async def test_restores_all_thresholds_at_once(self):
        c = make_controller(self.hass)
        await c.async_set_value("min_humidity", 65)
        await c.async_set_value("min_humidity_off", 60)
        await c.async_set_value("buffer_off", 0.5)
        await c.async_set_value("buffer_on", 3.5)
        await c.async_set_value("dewpoint_margin", 4.0)
        await c.async_set_value("min_battery", 40)
        await c.async_restore_defaults()
        self.assertEqual(
            c.values,
            {
                "buffer_on": 2.5,
                "buffer_off": 1.0,
                "dewpoint_margin": 2.0,
                "min_humidity": 55.0,
                "min_humidity_off": 55.0,
                "min_battery": 20.0,
            },
        )
        self.assertEqual(c._store.saved["values"]["min_humidity_off"], 55.0)

    async def test_restore_works_where_single_steps_would_be_rejected(self):
        # Ein-Feuchte 70 / Aus 68: nacheinander gesetzt würde 55 für "ein" abgelehnt (68 > 55)
        c = make_controller(self.hass)
        await c.async_set_value("min_humidity", 70)
        await c.async_set_value("min_humidity_off", 68)
        await c.async_restore_defaults()
        self.assertEqual((c.values["min_humidity"], c.values["min_humidity_off"]), (55.0, 55.0))

    async def test_restore_triggers_evaluation(self):
        set_climate(self.hass, *WINTER)
        c = make_controller(self.hass)
        await c.async_set_value("min_humidity", 80)
        self.hass.services.calls.clear()
        await c.async_restore_defaults()
        self.assertEqual(self.hass.services.switch_calls(), [("turn_on", ["switch.fan"])])


class FrontendTests(unittest.IsolatedAsyncioTestCase):
    async def test_card_is_registered_once_with_version(self):
        registered = []

        async def register(paths):
            registered.extend(paths)

        hass = types.SimpleNamespace(http=types.SimpleNamespace(async_register_static_paths=register))
        frontend_calls.clear()
        self.assertTrue(await integration.async_setup(hass, {}))
        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0].url_path, "/smart_ventilation_controller")
        self.assertTrue(os.path.isdir(registered[0].path))
        self.assertEqual(frontend_calls, ["/smart_ventilation_controller/smart-ventilation-card.js?v=9.9.9"])

    def test_served_files_exist(self):
        for name in ("smart-ventilation-card.js", "smart-ventilation-card.webp"):
            self.assertTrue(os.path.isfile(os.path.join(COMPONENT, "www", name)), name)

    def test_manifest_dependencies(self):
        with open(os.path.join(COMPONENT, "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["dependencies"], ["frontend", "http"])

    def test_config_schema(self):
        self.assertEqual(integration.CONFIG_SCHEMA, ("config_entry_only", "smart_ventilation_controller"))


if __name__ == "__main__":
    unittest.main()
