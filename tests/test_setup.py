"""Authentication failures stop setup/polling; transport failures remain retryable."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/onstar_uy'


class SetupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        class ConfigEntryError(Exception):
            pass
        class ConfigEntryAuthFailed(ConfigEntryError):
            pass
        class ConfigEntryNotReady(ConfigEntryError):
            pass
        self.auth_failed = ConfigEntryAuthFailed
        self.not_ready = ConfigEntryNotReady
        self.entry_error = ConfigEntryError
        exceptions = types.ModuleType('homeassistant.exceptions')
        exceptions.ConfigEntryError = ConfigEntryError
        exceptions.ConfigEntryAuthFailed = ConfigEntryAuthFailed
        exceptions.ConfigEntryNotReady = ConfigEntryNotReady
        class Coordinator:
            def __init__(self, hass, logger, **kwargs):
                self.update = kwargs['update_method']
            async def async_config_entry_first_refresh(self):
                await self.update()
        updates = types.ModuleType('homeassistant.helpers.update_coordinator')
        updates.DataUpdateCoordinator = Coordinator
        updates.UpdateFailed = type('UpdateFailed', (Exception,), {})
        self.update_failed = updates.UpdateFailed
        helpers = types.ModuleType('homeassistant.helpers')
        helpers.config_validation = types.SimpleNamespace(string=str, boolean=bool)
        vol = types.ModuleType('probatio')
        vol.Schema = lambda value, **kwargs: value
        vol.Required = vol.Optional = lambda value, **kwargs: value
        vol.All = lambda *args: args
        vol.Coerce = lambda value: value
        vol.Range = lambda **kwargs: kwargs
        vol.ALLOW_EXTRA = True
        spec = importlib.util.spec_from_file_location('setup_test_package.client', ROOT / 'client.py')
        client_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(client_module)
        self.auth_error = client_module.OnStarAuthError
        self.network_error = client_module.OnStarError
        self.client = types.SimpleNamespace(
            vehicles=lambda: [{'vin':'FAKE-A'}],
            health=lambda vin: {}, extra_readings=lambda vin: {}, location=lambda vin: None)
        credentials = types.ModuleType('setup_test_package.credentials')
        credentials.KEY_FILENAME = 'test.json'
        credentials.SigningKeyError = type('SigningKeyError', (self.network_error,), {})
        self.signing_error = credentials.SigningKeyError
        credentials.make_client = lambda *args: self.client
        spec = importlib.util.spec_from_file_location('setup_test_package', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'setup_test_package':self.module,
                'setup_test_package.client':client_module, 'setup_test_package.credentials':credentials,
                'probatio':vol,'homeassistant':types.ModuleType('homeassistant'),
                'homeassistant.helpers':helpers,'homeassistant.exceptions':exceptions,
                'homeassistant.helpers.update_coordinator':updates}):
            spec.loader.exec_module(self.module)
        self.hass = types.SimpleNamespace(data={},config=types.SimpleNamespace(path=lambda p:p),
            async_add_executor_job=AsyncMock(side_effect=lambda func,*args:func(*args)),
            config_entries=types.SimpleNamespace(async_forward_entry_setups=AsyncMock()))
        self.entry = types.SimpleNamespace(data={'vin':'FAKE-A','auto_refresh':False,'scan_interval':1800},entry_id='test')

    async def test_setup_auth_failure_is_not_retryable(self):
        self.client.vehicles = lambda: (_ for _ in ()).throw(self.auth_error('Rejected'))
        with self.assertRaises(self.auth_failed):
            await self.module.async_setup_entry(self.hass,self.entry)
        self.hass.config_entries.async_forward_entry_setups.assert_not_awaited()

    async def test_setup_transport_failure_is_retryable(self):
        self.client.vehicles = lambda: (_ for _ in ()).throw(self.network_error('Offline'))
        with self.assertRaises(self.not_ready):
            await self.module.async_setup_entry(self.hass,self.entry)

    async def test_missing_or_ambiguous_vehicle_is_entry_error(self):
        for vehicles, vin in [([], 'FAKE-A'), ([{'vin':'OTHER'}], 'FAKE-A'),
                              ([{'vin':'A'},{'vin':'B'}], None)]:
            with self.subTest(vehicles=vehicles):
                self.client.vehicles = lambda: vehicles
                self.entry.data['vin'] = vin
                with self.assertRaises(self.entry_error) as raised:
                    await self.module.async_setup_entry(self.hass,self.entry)
                self.assertNotIsInstance(raised.exception,self.not_ready)

    async def test_update_auth_failures_propagate_including_optional_queries(self):
        for method in ('health','extra_readings','location'):
            with self.subTest(method=method):
                original = getattr(self.client,method)
                def reject(vin):
                    raise self.auth_error('Rejected')
                setattr(self.client,method,reject)
                with self.assertRaises(self.auth_failed):
                    await self.module.async_setup_entry(self.hass,self.entry)
                setattr(self.client,method,original)

    async def test_update_transport_failure_is_update_failed(self):
        self.client.health = lambda vin: (_ for _ in ()).throw(self.network_error('Offline'))
        with self.assertRaises(self.update_failed):
            await self.module.async_setup_entry(self.hass,self.entry)

    async def test_invalid_client_configuration_does_not_retry(self):
        self.client.vehicles = lambda: (_ for _ in ()).throw(self.signing_error('Invalid client'))
        with self.assertRaises(self.entry_error) as raised:
            await self.module.async_setup_entry(self.hass, self.entry)
        self.assertNotIsInstance(raised.exception, self.not_ready)
        self.assertNotIsInstance(raised.exception, self.auth_failed)
