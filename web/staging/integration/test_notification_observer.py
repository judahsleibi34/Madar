"""Actual loopback HTTP alert injection; no providers, databases or messages."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import inspect_notification_worker as observer


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.metrics={name:0 for name in observer.NAMES};self.consuming=True;self.healthy=True
        test=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                if self.path=='/health':status=200 if test.healthy else 503;body=json.dumps({'status':'ok' if test.healthy else 'starting','consuming':test.consuming}).encode()
                elif self.path=='/metrics':status=200;body=''.join(observer.PREFIX+name+' '+str(value)+'\n' for name,value in test.metrics.items()).encode()
                else:status=404;body=b''
                self.send_response(status);self.end_headers();self.wfile.write(body)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.url='http://127.0.0.1:'+str(self.server.server_port)
    def inspect(self,previous=None):return observer.inspect(self.url,'a'*64,True,previous)
    def test_real_health_metrics_then_ownership_ack_and_backlog_alerts(self):
        before=self.inspect();self.assertEqual(before['status'],'PASS')
        self.metrics.update(ownership_lost=1,acknowledgement_failed=2,queue_depth=1,oldest_pending_age_seconds=300)
        result=self.inspect(before)
        self.assertEqual(set(result['alerts']),{'DELIVERY_OWNERSHIP_LOST','DELIVERY_ACKNOWLEDGEMENT_FAILED','NOTIFICATION_BACKLOG_AGE'})
        self.assertFalse(result['actions_performed'])
    def test_unhealthy_and_standby_consumption_violation_alert(self):
        self.healthy=False;self.consuming=False
        self.assertEqual(set(self.inspect()['alerts']),{'WORKER_UNHEALTHY','CONSUMPTION_AUTHORITY_MISMATCH'})
    def test_restart_cannot_turn_counter_reset_into_clean_pass(self):
        self.metrics['sent']=4;before=self.inspect();self.metrics['sent']=0
        result=self.inspect(before);self.assertTrue(result['counter_reset_observed']);self.assertEqual(result['status'],'PARTIAL')
        before['instance_id']='b'*64
        with self.assertRaises(RuntimeError):self.inspect(before)
    def test_nonloopback_credentials_redirect_scope_and_missing_metrics_refuse(self):
        for url in ('http://example.com:8090','http://user:secret@127.0.0.1:8090','http://127.0.0.1:8090/rpc','https://127.0.0.1:8090'):
            with self.subTest(url_kind=url.split(':')[0]),self.assertRaises(RuntimeError):observer.inspect(url,'a'*64,True)
        del self.metrics['ownership_lost']
        with self.assertRaises(RuntimeError):self.inspect()


if __name__=='__main__':unittest.main(verbosity=2)
