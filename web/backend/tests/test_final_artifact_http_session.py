"""Acceptance-client regression using a real owned HTTP fixture, no authorization."""
import ast
import re
import urllib.error
import urllib.request
from http.cookies import SimpleCookie
from types import SimpleNamespace
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
# Exercise the real HTTP client without importing the root-only execution runner.
path=WEB/'scripts/verify_final_application_artifacts.py'
source=ast.parse(path.read_text())
client=next(node for node in source.body if isinstance(node,ast.ClassDef) and node.name=='Session')
namespace={'urllib':urllib,'json':json,'SimpleCookie':SimpleCookie,'re':re}
def require(value,category):
    if not value:raise RuntimeError(category)
namespace['require']=require
exec(compile(ast.Module(body=[client],type_ignores=[]),str(path),'exec'),namespace)
module=SimpleNamespace(Session=namespace['Session'])

class ArtifactHttpSessionTests(unittest.TestCase):
    def test_cookie_and_header_renewal_is_used_for_next_write(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                self.send_response(200)
                if self.path=='/header':self.send_header('X-CSRF-Token','renewed')
                self.send_header('Set-Cookie','madar_csrf_token=renewed; Path=/; SameSite=None; Secure')
                self.end_headers();self.wfile.write(b'{}')
            def do_PUT(self):
                valid=self.headers.get('X-CSRF-Token')=='renewed' and 'madar_csrf_token=renewed' in self.headers.get('Cookie','')
                self.send_response(200 if valid else 403);self.end_headers();self.wfile.write(json.dumps({'accepted':valid}).encode())
        with HTTPServer(('127.0.0.1',0),Handler) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                for path in ('/header','/cookie'):
                    with self.subTest(path=path):
                        session=module.Session('http://127.0.0.1:'+str(server.server_port))
                        session.csrf='stale';session.cookies['madar_csrf_token']='stale'
                        self.assertEqual(session.request(path)[0],200)
                        self.assertTrue(session.ok('/write',{},'PUT')['accepted'])
            finally:server.shutdown();thread.join(timeout=2)
