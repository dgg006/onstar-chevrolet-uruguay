import base64
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'custom_components/onstar_uy'
spec = importlib.util.spec_from_file_location('credentials_test_package.client', SOURCE / 'client.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
package = types.ModuleType('credentials_test_package')
package.__path__ = []
const = types.ModuleType('credentials_test_package.const')
const.APP_CLIENT_ID = 'TEST_CLIENT'
const.APP_DEFAULTS = {'client_id':'TEST_CLIENT', 'client_secret':'default-test-key', 'app_version':'8.19.0'}
spec = importlib.util.spec_from_file_location('credentials_test_package.credentials', SOURCE / 'credentials.py')
credentials = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'credentials_test_package': package,
            'credentials_test_package.client': client, 'credentials_test_package.const': const}):
    spec.loader.exec_module(credentials)


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / credentials.KEY_FILENAME

    def write_key(self, key):
        self.path.write_text(json.dumps({'client_secret': key}), encoding='utf-8')

    def test_missing_file_preserves_existing_private_configuration(self):
        self.assertEqual(credentials.load_signing_key(self.path, 'legacy-test-key'), 'legacy-test-key')
        with self.assertRaises(credentials.SigningKeyError):
            credentials.load_signing_key(self.path)

    def test_file_takes_priority_and_invalid_file_does_not_fall_back(self):
        self.write_key('file-test-key')
        self.assertEqual(credentials.load_signing_key(self.path, 'legacy-test-key'), 'file-test-key')
        self.path.write_text('{invalid-json-private-content', encoding='utf-8')
        with self.assertRaises(credentials.SigningKeyError) as error:
            credentials.load_signing_key(self.path, 'legacy-test-key')
        self.assertNotIn('private-content', str(error.exception))

    def test_empty_or_invalid_key_never_authenticates(self):
        for key in ['', '   ', None, 123, {'unexpected': 'value'}]:
            self.write_key(key)
            c = credentials.make_client({'username': 'test@example.invalid', 'password': 'test-password', 'device_id': 'test-device'}, self.path)
            c._request = Mock()
            with self.assertRaises(credentials.SigningKeyError):
                c.login()
            c._request.assert_not_called()

    def test_editing_file_changes_signature_at_next_login(self):
        settings = {'username': 'test@example.invalid', 'password': 'test-password', 'device_id': 'test-device'}
        self.write_key('first-test-key')
        c = credentials.make_client(settings, self.path)
        c._request = Mock(return_value=(200, json.dumps({'access_token': 'test-token', 'scope': 'onstar', 'expires_in': 1799})))
        for key in ['first-test-key', 'second-test-key']:
            self.write_key(key)
            c.login()
            signed = c._request.call_args.args[1].decode()
            header, payload, signature = signed.split('.')
            expected = base64.urlsafe_b64encode(hmac.new(key.encode(), (header+'.'+payload).encode(), hashlib.sha256).digest()).decode().rstrip('=')
            self.assertEqual(signature, expected)
        self.assertNotIn('client_secret', settings)
        self.assertEqual(c._request.call_count, 2)

    def test_ui_pair_overrides_private_file_and_updates_headers(self):
        self.write_key('file-test-key')
        settings = {'username':'test@example.invalid','password':'test-password','device_id':'test-device',
                    'client_id':'TEST_OLD_CLIENT','client_secret':'ui-test-key','app_version':'8.11.0',
                    'client_configuration_override':True}
        c = credentials.make_client(settings, self.path)
        c._request = Mock(return_value=(200,json.dumps({'access_token':'test-token','scope':'onstar','expires_in':1799})))
        c.login()
        payload = c._request.call_args.args[1].decode().split('.')[1]
        self.assertEqual(json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))['client_id'], 'TEST_OLD_CLIENT')
        self.assertEqual(c.app_version,'8.11.0')

    def test_file_pair_changes_together_on_next_login(self):
        settings = {'username':'test@example.invalid','password':'test-password','device_id':'test-device'}
        c = credentials.make_client(settings,self.path)
        c._request = Mock(return_value=(200,json.dumps({'access_token':'test-token','scope':'onstar','expires_in':1799})))
        for client_id, version in [('TEST_A','8.11.0'),('TEST_B','8.19.0')]:
            self.path.write_text(json.dumps({'client_secret':'test-key','client_id':client_id,'app_version':version}))
            c.login()
            self.assertEqual((c.client_id,c.app_version),(client_id,version))

    def test_defaults_allow_new_installation_without_private_file(self):
        settings = {'username':'test@example.invalid','password':'test-password','device_id':'test-device'}
        self.assertEqual(credentials.load_client_configuration(settings,self.path),const.APP_DEFAULTS)
