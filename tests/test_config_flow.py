"""Tests für Einrichtung, Neu konfigurieren und Konfigurieren (Stromquelle)."""

from __future__ import annotations

import os
import sys
import types
import unittest

import ha_stubs  # noqa: F401

REPO = os.environ.get("REPO") or os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(REPO, "custom_components"))

from smart_ventilation_controller.config_flow import (  # noqa: E402
    SmartVentilationConfigFlow,
    SmartVentilationOptionsFlow,
)
from smart_ventilation_controller.const import DEFAULT_OPTIONS  # noqa: E402

SENSORS = {
    "indoor_temperature": "sensor.in_t",
    "indoor_humidity": "sensor.in_h",
    "outdoor_temperature": "sensor.out_t",
    "outdoor_humidity": "sensor.out_h",
    "fan_entity": "switch.fan",
    "additional_fans": [],
}
OPTIONS = {k: v for k, v in DEFAULT_OPTIONS.items() if k != "power_source"}


def hass():
    return types.SimpleNamespace(
        config=types.SimpleNamespace(language="de"),
        services=types.SimpleNamespace(async_services=lambda: {"notify": {}}),
    )


def entry(data, options):
    return types.SimpleNamespace(data=data, options=options)


def config_flow():
    flow = SmartVentilationConfigFlow()
    flow.hass = hass()
    return flow


def options_flow(data, options):
    flow = SmartVentilationOptionsFlow()
    flow.hass = hass()
    flow.config_entry = entry(data, options)
    return flow


class SetupTests(unittest.IsolatedAsyncioTestCase):
    async def test_form_contains_power_source(self):
        result = await config_flow().async_step_user()
        self.assertIn("power_source", result["schema"].schema)
        self.assertIn("battery_level", result["schema"].schema)

    async def test_grid_goes_to_options(self):
        result = await config_flow().async_step_user(
            {"name": "Keller", **SENSORS, "power_source": "grid", "battery_level": "sensor.x"}
        )
        self.assertEqual(result["type"], "create_entry")
        self.assertNotIn("power_source", result["data"])
        self.assertNotIn("battery_level", result["data"])
        self.assertEqual(result["options"]["power_source"], "grid")
        self.assertNotIn("battery_level", result["options"])

    async def test_battery_goes_to_options(self):
        result = await config_flow().async_step_user(
            {"name": "Keller", **SENSORS, "power_source": "battery", "battery_level": "sensor.akku"}
        )
        self.assertEqual(result["options"]["power_source"], "battery")
        self.assertEqual(result["options"]["battery_level"], "sensor.akku")
        self.assertNotIn("battery_level", result["data"])

    async def test_battery_without_sensor_shows_error(self):
        result = await config_flow().async_step_user(
            {"name": "Keller", **SENSORS, "power_source": "battery"}
        )
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"battery_level": "battery_level_required"})


class ReconfigureTests(unittest.IsolatedAsyncioTestCase):
    def flow(self, data):
        flow = config_flow()
        flow.reconfigure_entry = entry(data, {})
        return flow

    async def test_form_has_no_power_source(self):
        result = await self.flow(SENSORS).async_step_reconfigure()
        self.assertNotIn("power_source", result["schema"].schema)

    async def test_keeps_power_source_from_version_1_2_0(self):
        old = {**SENSORS, "power_source": "battery", "battery_level": "sensor.akku"}
        result = await self.flow(old).async_step_reconfigure({**SENSORS, "fan_entity": "switch.neu"})
        self.assertEqual(result["data"]["power_source"], "battery")
        self.assertEqual(result["data"]["battery_level"], "sensor.akku")
        self.assertEqual(result["data"]["fan_entity"], "switch.neu")

    async def test_cleared_optional_field_is_removed(self):
        old = {**SENSORS, "wall_temperature": "sensor.wand"}
        result = await self.flow(old).async_step_reconfigure(dict(SENSORS))
        self.assertNotIn("wall_temperature", result["data"])


class OptionsTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_entry_shows_power_source_as_grid(self):
        result = await options_flow(SENSORS, OPTIONS).async_step_init()
        self.assertIn("power_source", result["schema"].schema)
        self.assertEqual(result["schema"].suggested["power_source"], "grid")

    async def test_entry_from_1_2_0_shows_stored_battery(self):
        data = {**SENSORS, "power_source": "battery", "battery_level": "sensor.akku"}
        result = await options_flow(data, OPTIONS).async_step_init()
        self.assertEqual(result["schema"].suggested["power_source"], "battery")
        self.assertEqual(result["schema"].suggested["battery_level"], "sensor.akku")

    async def test_options_win_over_old_data(self):
        data = {**SENSORS, "power_source": "battery", "battery_level": "sensor.akku"}
        result = await options_flow(data, {**OPTIONS, "power_source": "grid"}).async_step_init()
        self.assertEqual(result["schema"].suggested["power_source"], "grid")

    async def test_save_battery(self):
        result = await options_flow(SENSORS, OPTIONS).async_step_init(
            {**OPTIONS, "power_source": "battery", "battery_level": "sensor.akku"}
        )
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["power_source"], "battery")
        self.assertEqual(result["data"]["battery_level"], "sensor.akku")

    async def test_save_battery_without_sensor_shows_error_and_keeps_input(self):
        user_input = {**OPTIONS, "power_source": "battery", "max_runtime": 90}
        result = await options_flow(SENSORS, OPTIONS).async_step_init(user_input)
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"battery_level": "battery_level_required"})
        self.assertEqual(result["schema"].suggested["max_runtime"], 90)

    async def test_save_grid_drops_sensor(self):
        result = await options_flow(SENSORS, OPTIONS).async_step_init(
            {**OPTIONS, "power_source": "grid", "battery_level": "sensor.akku"}
        )
        self.assertNotIn("battery_level", result["data"])


if __name__ == "__main__":
    unittest.main()
