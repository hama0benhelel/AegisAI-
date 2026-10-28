import unittest
from unittest.mock import patch
from monitoring_lab import CASES, Grafana, metric

class MonitoringHelperTests(unittest.TestCase):
    def setUp(self):
        self.grafana = Grafana.__new__(Grafana)
        self.labels = {'tenant_id':'tenant-a','user_id':'user-a'}
    def document(self,alerts,state='inactive',health='ok',error=''):
        return {'status':'success','data':{'groups':[{'rules':[{'name':CASES['injection']['title'],'health':health,'lastError':error,'state':state,'alerts':alerts}]}]}}
    def test_correct_actor_firing_and_pending(self):
        for state in ('firing','pending'):
            data=self.document([{'state':state,'labels':self.labels}],state)
            with patch.object(self.grafana,'get',return_value=data):
                self.assertEqual(self.grafana.state('injection',self.labels),state)
    def test_other_actor_is_not_attributed_to_client_a(self):
        data=self.document([{'state':'firing','labels':{'tenant_id':'tenant-b','user_id':'user-b'}}],'firing')
        with patch.object(self.grafana,'get',return_value=data):
            self.assertEqual(self.grafana.state('injection',self.labels),'normal')
    def test_error_and_uninitialized_are_not_success(self):
        with patch.object(self.grafana,'get',return_value=self.document([],health='err',error='query failed')):
            with self.assertRaises(RuntimeError):
                self.grafana.state('injection',self.labels)
        with patch.object(self.grafana,'get',return_value=self.document([],health='unknown')):
            self.assertEqual(self.grafana.state('injection',self.labels),'initializing')
    def test_metric_ignores_unlabelled_fallback_and_other_users(self):
        values=[{'metric':{},'value':[0,'0']},{'metric':self.labels,'value':[0,'3']},{'metric':{'tenant_id':'tenant-b','user_id':'user-b'},'value':[0,'9']}]
        with patch('monitoring_lab.loki',return_value=values):
            self.assertEqual(metric('injection',self.labels),3)
    def test_metric_failure_does_not_become_zero(self):
        with patch('monitoring_lab.loki',side_effect=RuntimeError('Loki error')):
            with self.assertRaises(RuntimeError):
                metric('injection',self.labels)

if __name__=='__main__':
    unittest.main(verbosity=2)
