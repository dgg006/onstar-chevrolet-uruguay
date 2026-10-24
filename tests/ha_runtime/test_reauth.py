"""Run with Home Assistant 2026.10 installed: python -m unittest discover -s tests/ha_runtime."""
import tempfile
import unittest
from types import MappingProxyType, SimpleNamespace
from unittest.mock import Mock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from custom_components.onstar_uy.config_flow import OnStarConfigFlow
from custom_components.onstar_uy.client import OnStarAuthError


class RealHomeAssistantReauthTests(unittest.IsolatedAsyncioTestCase):
    async def test_password_replacement_uses_real_entry_and_reload_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            hass = HomeAssistant(directory)
            hass.config_entries = ConfigEntries(hass, {})
            values = {'username':'test@example.invalid','password':'old','vin':'FAKE-A',
                      'device_id':'test-device','client_id':'test-app','scan_interval':1800}
            entry = ConfigEntry(domain='onstar_uy', data=values, options={}, source='user',
                title='Test OnStar', version=1, minor_version=1, unique_id=None,
                discovery_keys=MappingProxyType({}), subentries_data=None)
            hass.config_entries._entries[entry.entry_id] = entry
            flow = OnStarConfigFlow()
            flow.hass = hass
            flow.handler = 'onstar_uy'
            flow.context = {'source':'reauth','entry_id':entry.entry_id}
            form = await flow.async_step_reauth(entry.data)
            self.assertEqual(form['step_id'], 'reauth_confirm')
            self.assertEqual(form['data_schema']({'password':'new'}), {'password':'new'})
            client = SimpleNamespace(vehicles=Mock(side_effect=OnStarAuthError('Rejected')))
            with patch.object(flow, '_client', return_value=client), \
                 patch.object(hass.config_entries, 'async_schedule_reload') as reload:
                failed = await flow.async_step_reauth_confirm({'password':'wrong'})
                self.assertEqual(failed['errors'], {'base':'invalid_auth'})
                self.assertEqual(entry.data['password'], 'old')
                reload.assert_not_called()
                client.vehicles.side_effect = None
                client.vehicles.return_value = [{'vin':'FAKE-A'}]
                result = await flow.async_step_reauth_confirm({'password':'new'})
                self.assertEqual(result['reason'], 'reauth_successful')
                self.assertEqual(dict(entry.data), dict(values, password='new'))
                reload.assert_called_once_with(entry.entry_id)
            await hass.async_stop()
