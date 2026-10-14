import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


class DiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_diagnostics_do_not_export_credentials_or_vehicle_data(self):
        package=types.ModuleType('diagnostics_test_package'); package.DOMAIN='onstar_uy'; package.__path__=[]
        spec=importlib.util.spec_from_file_location('diagnostics_test_package.diagnostics',Path(__file__).resolve().parents[1]/'custom_components/onstar_uy/diagnostics.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'diagnostics_test_package':package}):spec.loader.exec_module(module)
        entry=types.SimpleNamespace(entry_id='test-entry',data={'username':'test-private-email','password':'test-private-password','client_secret':'test-private-key','vin':'test-private-vin'})
        runtime={'client':types.SimpleNamespace(app_version='8.19.0',_token='test-private-token'),
                 'coordinator':types.SimpleNamespace(last_update_success=True,data={'location':'test-private-location'})}
        hass=types.SimpleNamespace(data={'onstar_uy':{'test-entry':runtime}})
        result=await module.async_get_config_entry_diagnostics(hass,entry)
        self.assertTrue(result['loaded'])
        self.assertNotIn('test-private',json.dumps(result))
