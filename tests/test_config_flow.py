"""Onboarding uses fictitious accounts and vehicles, without contacting GM."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch


class ConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        class Flow:
            def __init_subclass__(cls, **kwargs):
                pass

            def _async_current_entries(self):
                return []

            def async_show_form(self, **kwargs):
                return {'type': 'form', **kwargs}

            def async_create_entry(self, **kwargs):
                return {'type': 'create_entry', **kwargs}

            def async_abort(self, **kwargs):
                return {'type': 'abort', **kwargs}

            def _get_reconfigure_entry(self):
                return self.entry

            def async_update_reload_and_abort(self, entry, data_updates):
                self.saved_updates = data_updates
                return {'type':'abort','reason':'reconfigure_successful'}

        ha = types.ModuleType('homeassistant')
        ha.config_entries = types.SimpleNamespace(ConfigFlow=Flow)
        vol = types.ModuleType('probatio')
        vol.Schema = lambda value, **kwargs: value
        vol.Required = vol.Optional = lambda value, **kwargs: value
        vol.In = lambda value: value
        selector = types.ModuleType('homeassistant.helpers.selector')
        selector.TextSelector = lambda value: value
        selector.TextSelectorConfig = lambda **kwargs: kwargs
        selector.TextSelectorType = types.SimpleNamespace(PASSWORD='password')
        package = types.ModuleType('flow_test_package')
        package.__path__ = []
        package.DOMAIN = 'onstar_uy'
        client = types.ModuleType('flow_test_package.client')
        client.OnStarError = RuntimeError
        self.vehicles = []
        self.client_args = None

        def factory(*args):
            self.client_args = args
            return types.SimpleNamespace(vehicles=lambda: self.vehicles)

        client.OnStarClient = factory
        const = types.ModuleType('flow_test_package.const')
        const.APP_CLIENT_ID = 'test-app-id'
        const.APP_DEFAULTS = {'client_id':'test-app-id','client_secret':'default-test-key','app_version':'8.19.0'}
        credentials = types.ModuleType('flow_test_package.credentials')
        credentials.KEY_FILENAME = 'onstar_uy_private.json'
        credentials.SigningKeyError = type('SigningKeyError', (RuntimeError,), {})
        credentials.make_client = lambda values, path: factory(values['username'], values['password'], values.get('client_secret', ''), values['device_id'], values['client_id'])
        credentials.load_client_configuration = lambda values,path: dict(const.APP_DEFAULTS, **{key:values[key] for key in const.APP_DEFAULTS if values.get(key)})
        data_entry = types.ModuleType('homeassistant.data_entry_flow')
        data_entry.section = lambda schema,options: schema
        path = Path(__file__).resolve().parents[1] / 'custom_components/onstar_uy/config_flow.py'
        spec = importlib.util.spec_from_file_location('flow_test_package.config_flow', path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'homeassistant': ha, 'probatio': vol,
                    'homeassistant.helpers.selector': selector,
                    'homeassistant.data_entry_flow':data_entry,
                    'flow_test_package': package, 'flow_test_package.client': client,
                    'flow_test_package.credentials': credentials,
                    'flow_test_package.const': const}):
            spec.loader.exec_module(module)
        self.flow = module.OnStarConfigFlow()
        self.flow.hass = types.SimpleNamespace(
            config=types.SimpleNamespace(path=lambda name: name),
            async_add_executor_job=AsyncMock(side_effect=lambda func,*args: func(*args)))
        vol.All = lambda *args: args
        vol.Coerce = lambda value:value
        vol.Range = lambda **kwargs:kwargs

    async def test_single_vehicle_uses_private_client_configuration(self):
        form = await self.flow.async_step_user()
        self.assertEqual(set(form['data_schema']), {'username', 'password', 'advanced'})
        self.vehicles = [{'vin': 'FAKE-VEHICLE-A', 'model': 'Test car'}]
        result = await self.flow.async_step_user({'username': 'test@example.invalid', 'password': 'test-password', 'client_secret': 'test-client-key'})
        self.assertEqual(result['type'], 'create_entry')
        self.assertEqual(result['data']['vin'], 'FAKE-VEHICLE-A')
        self.assertEqual(result['data']['client_secret'], 'test-client-key')
        self.assertEqual(self.client_args[2], 'test-client-key')

    async def test_multiple_vehicles_require_valid_selection(self):
        self.vehicles = [{'vin': 'FAKE-VEHICLE-A'}, {'vin': 'FAKE-VEHICLE-B'}]
        result = await self.flow.async_step_user({'username': 'test@example.invalid', 'password': 'test-password', 'client_secret': 'test-client-key'})
        self.assertEqual(result['step_id'], 'select_vehicle')
        result = await self.flow.async_step_select_vehicle({'vin': 'UNRELATED-VEHICLE'})
        self.assertEqual(result['type'], 'form')
        result = await self.flow.async_step_select_vehicle({'vin': 'FAKE-VEHICLE-B'})
        self.assertEqual(result['data']['vin'], 'FAKE-VEHICLE-B')

    async def test_empty_account_does_not_create_entry(self):
        result = await self.flow.async_step_user({'username': 'test@example.invalid', 'password': 'test-password', 'client_secret': 'test-client-key'})
        self.assertEqual(result['errors'], {'base': 'no_vehicles'})
        self.assertEqual(result['type'], 'form')

    async def test_existing_account_aborts_without_network(self):
        self.flow._async_current_entries = lambda: [object()]
        result = await self.flow.async_step_user({'username': 'test@example.invalid', 'password': 'test-password', 'client_secret': 'test-client-key'})
        self.assertEqual(result['type'], 'abort')
        self.flow.hass.async_add_executor_job.assert_not_awaited()

    async def test_changed_client_requires_matching_key(self):
        self.vehicles = [{'vin':'FAKE-VEHICLE-A'}]
        result = await self.flow.async_step_user({'username':'test@example.invalid','password':'test-password',
                'advanced':{'client_id':'OTHER_CLIENT','app_version':'8.11.0'}})
        self.assertEqual(result['errors'],{'base':'client_key_error'})
        self.assertIsNone(self.client_args)

    async def test_failed_reconfigure_preserves_entry(self):
        values = {'username':'test@example.invalid','password':'test-password','device_id':'test-device',
                  'client_id':'test-app-id','vin':'FAKE-VEHICLE-A'}
        self.flow.entry = types.SimpleNamespace(data=dict(values))
        def reject(*args):
            raise RuntimeError('Generic failure')
        self.flow._client = reject
        result = await self.flow.async_step_reconfigure({'advanced':{'client_id':'OTHER_CLIENT','client_secret':'new-test-key','app_version':'8.11.0'}})
        self.assertEqual(result['errors'],{'base':'cannot_connect'})
        self.assertEqual(self.flow.entry.data,values)
        self.assertFalse(hasattr(self.flow,'saved_updates'))

    async def test_successful_reconfigure_saves_whole_pair(self):
        self.flow.entry = types.SimpleNamespace(data={'username':'test@example.invalid','password':'test-password',
             'device_id':'test-device','client_id':'test-app-id','vin':'FAKE-VEHICLE-A'})
        self.vehicles = [{'vin':'FAKE-VEHICLE-A'}]
        result = await self.flow.async_step_reconfigure({'advanced':{'client_id':'OTHER_CLIENT','client_secret':'new-test-key','app_version':'8.11.0'}})
        self.assertEqual(result['reason'],'reconfigure_successful')
        self.assertEqual(self.flow.saved_updates['app_version'],'8.11.0')
        self.assertTrue(self.flow.saved_updates['client_configuration_override'])
