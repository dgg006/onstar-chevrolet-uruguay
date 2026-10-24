"""Regression for HA overwriting ButtonEntity.state when a button is pressed."""
import importlib.util
import asyncio
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch


class ButtonTests(unittest.IsolatedAsyncioTestCase):
    async def test_press_preserves_refresh_state_after_ha_sets_button_timestamp(self):
        button_module = types.ModuleType('homeassistant.components.button')
        coordinator_module = types.ModuleType('homeassistant.helpers.update_coordinator')

        class ButtonEntity:
            state = 'last-pressed-timestamp'

        class CoordinatorEntity:
            def __init__(self, coordinator):
                self.coordinator = coordinator

        button_module.ButtonEntity = ButtonEntity
        coordinator_module.CoordinatorEntity = CoordinatorEntity
        package = types.ModuleType('button_test_package')
        package.DOMAIN = 'onstar_uy'
        package.__path__ = []
        exceptions = types.ModuleType('homeassistant.exceptions')
        exceptions.HomeAssistantError = RuntimeError
        client_module = types.ModuleType('button_test_package.client')
        client_module.OnStarError = RuntimeError
        client_module.OnStarAuthError = type("OnStarAuthError", (RuntimeError,), {})
        path = Path(__file__).resolve().parents[1] / 'custom_components/onstar_uy/button.py'
        spec = importlib.util.spec_from_file_location('button_test_package.button', path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'button_test_package': package,
                    'homeassistant.components.button': button_module,
                    'homeassistant.exceptions': exceptions,
                    'button_test_package.client': client_module,
                    'homeassistant.helpers.update_coordinator': coordinator_module}):
            spec.loader.exec_module(module)
            coordinator = types.SimpleNamespace(async_request_refresh=AsyncMock())
            refresh_state = {'force_refresh': False}
            button = module.OnStarRefreshButton({'state': refresh_state, 'coordinator': coordinator, 'vin': 'test-vin'})
            # HA sets the public state to its press timestamp before async_press.
            button.state = 'new-last-pressed-timestamp'
            await button.async_press()
            self.assertTrue(refresh_state['force_refresh'])
            coordinator.async_request_refresh.assert_awaited_once()

            lock = asyncio.Lock()
            await lock.acquire()
            state = {'client': types.SimpleNamespace(control=lambda *args: 'SUCCESS'),
                     'vin': 'test-vin', 'control_lock': lock, 'entry': types.SimpleNamespace(async_start_reauth=Mock())}
            activate = module.OnStarControlButton(state, 'honk', 'Bocina', 'mdi:bullhorn')
            with self.assertRaisesRegex(RuntimeError, 'en curso'):
                await activate.async_press()
            stop = module.OnStarControlButton(state, 'cancel_honk', 'Apagar', 'mdi:bullhorn')
            stop.hass = types.SimpleNamespace(async_add_executor_job=AsyncMock(return_value='SUCCESS'))
            stop.async_write_ha_state = lambda: None
            await stop.async_press()
            stop.hass.async_add_executor_job.assert_awaited_once()
            self.assertEqual(stop.extra_state_attributes['resultado_ultimo_comando'], 'SUCCESS')
            lock.release()

            for error, reauth in [(client_module.OnStarAuthError('Rejected'), True),
                                   (RuntimeError('Offline'), False)]:
                state['entry'].async_start_reauth.reset_mock()
                stop.hass.async_add_executor_job = AsyncMock(side_effect=error)
                with self.assertRaises(RuntimeError):
                    await stop.async_press()
                stop.hass.async_add_executor_job.assert_awaited_once()
                self.assertEqual(state['entry'].async_start_reauth.called, reauth)
