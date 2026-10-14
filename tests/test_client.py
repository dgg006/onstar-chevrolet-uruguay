import base64
import importlib.util
import json
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, patch

path = Path(__file__).resolve().parents[1] / 'custom_components/onstar_uy/client.py'
spec = importlib.util.spec_from_file_location('client', path)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


def session(scope='onstar gmoc priv', expires=1799):
    return json.dumps({'access_token': 'test-token', 'scope': scope, 'expires_in': expires})


class ClientTests(unittest.TestCase):
    def test_headers_use_configured_app_version(self):
        c = client.OnStarClient('test@example.invalid','test-password','test-key','test-device',app_version='8.11.0')
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status = 200
        response.read.return_value = b'{}'
        opener = Mock()
        opener.open.return_value = response
        with patch.object(client.urllib.request,'build_opener',return_value=opener):
            c._request('/api/v1/account/vehicles',token='test-token')
        headers = {k.lower():v for k,v in opener.open.call_args.args[0].header_items()}
        self.assertEqual(headers['app-version'],'8.11.0')
        self.assertEqual(headers['appversion'],'myOwner-chevrolet-android-8.11.0-0')

    def test_control_acceptance_is_not_completion_and_never_replays_post(self):
        c = self.make_client()
        c._token, c._expires = 'test-token', time.monotonic() + 1000
        c._request = Mock(side_effect=[(202, '{"requestId":"test-request"}'),
                                      (200, '{"status":"IN_PROGRESS"}'),
                                      (200, '{"status":"SUCCESS"}')])
        with patch.object(client.time, 'sleep'):
            self.assertEqual(c.control('test-vin', 'unlock'), 'SUCCESS')
        self.assertEqual(sum(call.kwargs.get('method') == 'POST' for call in c._request.call_args_list), 1)

    def test_control_401_and_transport_uncertainty_do_not_retry_actuation(self):
        for failure in [(401, 'private'), client.OnStarError('Sin conexión')]:
            c = self.make_client()
            c._token, c._expires = 'test-token', time.monotonic() + 1000
            c._request = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
            with self.assertRaises(client.OnStarError):
                c.control('test-vin', 'honk')
            self.assertEqual(c._request.call_count, 1)

    def test_control_short_timeout_does_not_claim_failure_or_replay(self):
        c = self.make_client()
        c._token, c._expires = 'test-token', time.monotonic() + 1000
        c._request = Mock(return_value=(202, '{"requestId":"test-request"}'))
        with self.assertRaisesRegex(client.OnStarError, 'pudo ejecutarse'):
            c.control('test-vin', 'flash', timeout=0)
        self.assertEqual(c._request.call_count, 1)

    def test_unknown_control_is_rejected_before_network(self):
        c = self.make_client()
        c._request = Mock()
        with self.assertRaises(client.OnStarError):
            c.control('test-vin', 'remote_start')
        c._request.assert_not_called()

    def make_client(self):
        return client.OnStarClient('test-user', 'test-password', 'test-secret', 'test-device')

    def test_observed_jwt_envelope_and_json(self):
        body = session()
        envelope = 'header.' + base64.urlsafe_b64encode(body.encode()).decode().rstrip('=') + '.signature'
        self.assertEqual(client.decode_response(envelope), json.loads(body))
        self.assertEqual(client.decode_response(body), json.loads(body))

    def test_missing_permission_never_sends_vehicle_request(self):
        c = self.make_client()
        c._request = Mock(return_value=(200, session(scope='gmoc')))
        with self.assertRaises(client.OnStarError):
            c.vehicles()
        self.assertEqual(c._request.call_count, 1)
        self.assertIsNone(c._token)

    def test_reuses_session_and_renews_expired_session(self):
        c = self.make_client()
        c._request = Mock(side_effect=[(200, session()), (200, '{}'), (200, '{}'),
                                      (200, session()), (200, '{}')])
        c.get('/test')
        c.get('/test')
        self.assertEqual(c._request.call_count, 3)
        c._expires = time.monotonic() - 1
        c.get('/test')
        self.assertEqual(c._request.call_count, 5)

    def test_401_reauthenticates_once(self):
        c = self.make_client()
        c._request = Mock(side_effect=[(200, session()), (401, 'private'),
                                      (200, session()), (401, 'private')])
        with self.assertRaisesRegex(client.OnStarError, 'HTTP 401'):
            c.get('/test')
        self.assertEqual(c._request.call_count, 4)

    def test_errors_do_not_include_private_response(self):
        c = self.make_client()
        c._request = Mock(return_value=(403, 'private-account password token'))
        with self.assertRaises(client.OnStarError) as raised:
            c.login()
        self.assertNotIn('private-account', str(raised.exception))
        self.assertNotIn('password', str(raised.exception))

    def test_zero_and_original_timestamp_are_preserved(self):
        health = {'cts': 'outer', 'diagnostics': [{'cts': 'group', 'diagnosticElements': [
            {'name': 'FUEL_LEVEL', 'value': '0', 'uom': '%', 'cts': 'vehicle'},
            {'name': 'ODO_READ', 'value': '0', 'uom': 'KM'}]}]}
        data = client.health_readings(health)
        self.assertEqual(data['FUEL_LEVEL'], {'value': '0', 'unit': '%', 'updated_at': 'vehicle'})
        self.assertEqual(data['ODO_READ']['updated_at'], 'group')

    def test_location_zero_coordinates_and_timestamp(self):
        c = self.make_client()
        c.get = Mock(return_value={'telemetry': {'occurredTs': 'vehicle-time',
            'data': {'position': {'lat': 0, 'lng': 0}, 'session': {'updatePending': 'NONE'}}}})
        self.assertEqual(c.location('test-vin')['latitude'], 0)
        self.assertEqual(c.location('test-vin')['updated_at'], 'vehicle-time')
        self.assertIn('sms=false', c.get.call_args[0][0])

    def test_location_rejects_invalid_coordinates(self):
        for lat in [91, float('nan'), None]:
            c = self.make_client()
            c.get = Mock(return_value={'telemetry': {'data': {'position': {'lat': lat, 'lng': 0}}}})
            with self.assertRaises(client.OnStarError):
                c.location('test-vin')

    def test_202_is_an_acknowledgement_not_an_error(self):
        c = self.make_client()
        c._request = Mock(side_effect=[(200, session()), (202, '{"requestId":"test-id"}')])
        self.assertEqual(c._json_request('/test', 'POST')['requestId'], 'test-id')

    def test_refresh_polls_and_uses_live_location_payload(self):
        c = self.make_client()
        c._json_request = Mock(side_effect=[{'requestId': 'location-id'}, {'requestId': 'health-id'}])
        c.get = Mock(side_effect=[{'status': 'IN_PROGRESS'}, {'status': 'SUCCESS'},
            {'status': 'SUCCESS', 'payload': {'location': {'lat': '0', 'long': '0'},
                                            'timeStamp': '2026-01-01T12:00:00Z'}}])
        with patch.object(client.time, 'sleep'):
            result = c.refresh('test-vin')
        self.assertEqual(result['location'], 'SUCCESS')
        self.assertEqual(result['health'], 'SUCCESS')
        self.assertEqual(result['position']['latitude'], 0)
        self.assertEqual(result['position']['updated_at'], '2026-01-01T12:00:00Z')
        self.assertIn('/vh/vehiclehealth/v1/healthstatus/probe/', c.get.call_args_list[1].args[0])
        self.assertEqual(c.refresh('test-vin'), result)
        self.assertEqual(c._json_request.call_count, 2)

    def test_refresh_failure_never_claims_new_location(self):
        c = self.make_client()
        c._json_request = Mock(side_effect=[{'requestId': 'location-id'}, {'requestId': 'health-id'}])
        c.get = Mock(return_value={'status': 'FAILED'})
        result = c.refresh('test-vin')
        self.assertEqual(result['location'], 'FAILED')
        self.assertIsNone(result['position'])

    def test_refresh_timeout_is_bounded(self):
        c = self.make_client()
        c._json_request = Mock(side_effect=[{'requestId': 'location-id'}, {'requestId': 'health-id'}])
        c.get = Mock(return_value={'status': 'IN_PROGRESS'})
        result = c.refresh('test-vin', timeout=0)
        self.assertEqual(result['health'], 'TIMEOUT')
        self.assertEqual(result['location'], 'TIMEOUT')
        c.get.assert_not_called()

    def test_empty_extra_states_are_not_invented(self):
        c = self.make_client()
        c._json_request = Mock(return_value={'data': {'vehicle': {'vehicleStatus': {
            'diagnostics': {'LEFT_REAR_DOOR_AJAR_STATUS': None,
                            'RIGHT_REAR_DOOR_AJAR_STATUS': {'value': None}}}}}})
        self.assertEqual(c.extra_readings('test-vin'), {})

    def test_extra_state_zero_is_preserved(self):
        c = self.make_client()
        c._json_request = Mock(return_value={'data': {'vehicle': {'vehicleStatus': {
            'diagnostics': {'LEFT_REAR_DOOR_AJAR_STATUS': {'value': 0, 'cts': 'test-date'}}}}}})
        self.assertEqual(c.extra_readings('test-vin')['LEFT_REAR_DOOR_AJAR_STATUS']['value'], 0)


if __name__ == '__main__':
    unittest.main()
