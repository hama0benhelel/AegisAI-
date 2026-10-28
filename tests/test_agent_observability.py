import io
import json
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from uuid import uuid4
from fastapi import HTTPException
from app.agent_events import observed_agent_call

class AgentObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.user = {'id': uuid4(), 'tenant_id': uuid4()}
        self.request = SimpleNamespace(state=SimpleNamespace(trace_id=str(uuid4())))
    def test_failed_call_is_logged_once_without_exception_details(self):
        for resource in ('water', 'energy', 'gas'):
            for status, reason in ((502, 'invalid_agent_response'), (503, 'agent_unavailable')):
                with self.subTest(resource=resource,status=status):
                    @observed_agent_call(resource)
                    def fail(rows, user, request):
                        raise HTTPException(status, 'secret-password-for-test and raw prompt')
                    output = io.StringIO()
                    with redirect_stdout(output), self.assertRaises(HTTPException) as error:
                        fail([], self.user, self.request)
                    self.assertEqual(error.exception.status_code, status)
                    lines = output.getvalue().splitlines()
                    self.assertEqual(len(lines), 1)
                    event = json.loads(lines[0])
                    self.assertEqual(event['event_type'], 'agent_call_failed')
                    self.assertEqual(event['target_service'], resource + '-agent')
                    self.assertEqual(event['trace_id'], self.request.state.trace_id)
                    self.assertEqual(event['tenant_id'], str(self.user['tenant_id']))
                    self.assertEqual(event['user_id'], str(self.user['id']))
                    self.assertEqual(event['reason'], reason)
                    self.assertNotIn('secret-password', output.getvalue())
                    self.assertNotIn('raw prompt', output.getvalue())
    def test_invalid_input_is_not_counted_as_outage(self):
        @observed_agent_call('gas')
        def reject(rows,user,request):
            raise HTTPException(422, 'invalid series')
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(HTTPException):
            reject([], self.user, self.request)
        self.assertEqual(output.getvalue(), '')
    def test_success_is_unchanged_and_does_not_log_failure(self):
        result = {'agent': 'gas'}
        @observed_agent_call('gas')
        def success(rows,user,request):
            return result
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertIs(success([],self.user,self.request), result)
        self.assertEqual(output.getvalue(), '')
    def test_only_known_service_names_are_allowed(self):
        with self.assertRaises(ValueError):
            observed_agent_call('client-controlled-url')
    def test_all_adapters_are_instrumented(self):
        from app.water_client import analyze_water
        from app.energy_client import analyze_energy
        from app.gas_client import analyze_gas
        for function in (analyze_water, analyze_energy, analyze_gas):
            self.assertTrue(hasattr(function, '__wrapped__'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
