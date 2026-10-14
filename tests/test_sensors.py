import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


def load_platform(name):
    package = types.ModuleType('sensor_test_package')
    package.DOMAIN = 'onstar_uy'
    package.__path__ = []
    platform = types.ModuleType('homeassistant.components.' + name)
    coordinator = types.ModuleType('homeassistant.helpers.update_coordinator')
    class CoordinatorEntity:
        def __init__(self, value): self.coordinator = value
    coordinator.CoordinatorEntity = CoordinatorEntity
    platform.SensorEntity = type('SensorEntity', (), {})
    platform.SensorStateClass = types.SimpleNamespace(MEASUREMENT='measurement')
    platform.BinarySensorEntity = type('BinarySensorEntity', (), {})
    platform.BinarySensorDeviceClass = types.SimpleNamespace(PROBLEM='problem')
    path = Path(__file__).resolve().parents[1] / ('custom_components/onstar_uy/' + name + '.py')
    spec = importlib.util.spec_from_file_location('sensor_test_package.' + name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'sensor_test_package': package,
         'homeassistant.components.' + name: platform,
         'homeassistant.helpers.update_coordinator': coordinator}):
        spec.loader.exec_module(module)
    return module


class SensorTests(unittest.TestCase):
    def state(self, readings):
        return {'vin': 'test-vin', 'vehicle': {'model': 'test-model'},
                'coordinator': types.SimpleNamespace(data={'readings': readings})}

    def test_display_precision_does_not_truncate_reading(self):
        module = load_platform('sensor')
        sensor = module.OnStarSensor(self.state({'ODO_READ': {'value': '1234.56789', 'unit': 'KM'}}), *module.SENSORS[0])
        self.assertEqual(sensor.native_value, 1234.56789)
        self.assertEqual(sensor._attr_suggested_display_precision, 1)

    def test_experimental_absence_is_unknown_not_closed(self):
        module = load_platform('sensor')
        for description in module.SENSORS:
            if description[-1]:
                sensor = module.OnStarSensor(self.state({}), *description)
                self.assertIsNone(sensor.native_value)
                self.assertTrue(sensor.extra_state_attributes['experimental'])

    def test_wrong_units_are_not_mislabeled(self):
        module = load_platform('sensor')
        sensor = module.OnStarSensor(self.state({'ODO_READ': {'value': '12', 'unit': 'MI'}}), *module.SENSORS[0])
        self.assertIsNone(sensor.native_value)

    def test_fluid_warning_missing_is_not_ok(self):
        module = load_platform('binary_sensor')
        for value, expected in [('FALSE', False), ('TRUE', True), (None, None), ('UNKNOWN', None)]:
            sensor = module.FluidWarning(self.state({'BRAKE_FLUID_LOW': {'value': value}}), 'BRAKE_FLUID_LOW', 'test')
            self.assertIs(sensor.is_on, expected)
