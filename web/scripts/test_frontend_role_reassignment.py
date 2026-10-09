#!/usr/bin/env python3
"""Narrow isolated Nginx/Docker DNS fixture; no production resources or images.

Retain actual routing results. Only uniquely test-owned containers/network are
removed during this fixture's lifecycle. No application acceptance PASS issued.
"""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

NGINX='sha256:4a73073bd557c65b759505da037898b61f1be6cbcc3c2c3aeac22d2a470c1752'
PYTHON='sha256:916a7fb975afcfd3a7d10035aa7b8c49cddda68914a25b4128e49c32969335cd'
SERVER="""import os,json
from http.server import BaseHTTPRequestHandler,HTTPServer
class H(BaseHTTPRequestHandler):
 def do_GET(self):
  body=json.dumps({'role':os.environ['FIXTURE_ROLE'],'path':self.path}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
HTTPServer(('0.0.0.0',8000),H).serve_forever()
"""


def run(args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=30)
    if result.returncode:
        stage=':'.join(args[:3]) if args[:2]==['docker','network'] else ':'.join(args[:2])
        raise RuntimeError('frontend_dns_fixture_command_failed:'+stage)
    return result.stdout.strip()


def test(template):
    prefix='madar-routing-dns-fixture-'+uuid.uuid4().hex[:12];network=prefix+'-net';owned=[]
    with tempfile.TemporaryDirectory(prefix='madar-nginx-dns-fixture-') as scratch:
        root=Path(scratch);root.chmod(0o700);config=root/'nginx.conf';headers=root/'headers.conf'
        headers.write_text('');headers.chmod(0o444)
        config.write_text('pid /tmp/nginx.pid; error_log /dev/stderr; events {} http {\n'+template.decode()+'\n}');config.chmod(0o444)
        ids=run(['docker','network','ls','-q']).splitlines()
        rows=json.loads(run(['docker','network','inspect',*ids]))
        occupied=[ipaddress.ip_network(item['Subnet']) for row in rows for item in row.get('IPAM',{}).get('Config') or [] if item.get('Subnet')]
        routes=json.loads(run(['ip','-j','route']))
        occupied += [ipaddress.ip_network(row['dst'],strict=False) for row in routes if row.get('dst') not in {None,'default'}]
        subnet=next((str(candidate) for index in range(256) for candidate in [ipaddress.ip_network(f'10.251.{index}.0/24')] if not any(candidate.overlaps(other) for other in occupied if candidate.version==other.version)),None)
        if subnet is None:raise RuntimeError('frontend_dns_fixture_no_free_subnet')
        run(['docker','network','create','--internal','--subnet',subnet,network])
        def server(suffix,role,*,alias=None,address=None):
            name=prefix+'-'+suffix
            args=['docker','run','--pull','never','--detach','--name',name,'--network',network,
                  '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','128m','--cpus','0.5','--pids-limit','32','--user','65534:65534','--env','FIXTURE_ROLE='+role]
            if alias:args+=['--network-alias',alias]
            if address:args+=['--ip',address]
            args+=[PYTHON,'python','-B','-c',SERVER];run(args);owned.append(name);return name
        try:
            old=server('old-backend','A',alias='backend');front=prefix+'-frontend'
            args=['docker','run','--pull','never','--detach','--name',front,'--network',network,'--user','101:101',
                  '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','128m','--cpus','0.5','--pids-limit','32',
                  '--tmpfs','/tmp:rw,nosuid,nodev,size=16m,mode=1777','--tmpfs','/var/cache/nginx:rw,nosuid,nodev,size=16m,mode=1777',
                  '--mount',f'type=bind,src={config},dst=/fixture-nginx.conf,readonly']
            for name in ('security_headers','admin_preview_frame_headers','storefront_frame_headers'):
                args+=['--mount',f'type=bind,src={headers},dst=/etc/nginx/conf.d/includes/{name}.conf,readonly']
            args+=['--entrypoint','nginx',NGINX,'-c','/fixture-nginx.conf','-g','daemon off;'];run(args);owned.append(front)
            def request(path):
                return json.loads(run(['docker','exec',front,'wget','-qO-','-T','3','http://127.0.0.1:8080'+path]))
            def await_role(role,path):
                started=time.monotonic()
                while time.monotonic()-started<30:
                    try:
                        result=request(path)
                        if result.get('role')==role:return result
                    except (RuntimeError,ValueError):pass
                    time.sleep(0.25)
                raise RuntimeError('frontend_dns_fixture_convergence_failed')
            paths={'/api/health/version?fixture=1':'/health/version?fixture=1',
                   '/api/auth/v1/verify?token=synthetic':'/auth/v1/verify?token=synthetic',
                   '/uploads/fixture.png?version=1':'/uploads/fixture.png?version=1',
                   '/site/fixture/hello?x=1':'/public/legacy/site/fixture/hello?x=1'}
            before={}
            for path,expected in paths.items():
                result=await_role('A',path)
                if result['path']!=expected:raise RuntimeError('frontend_dns_fixture_uri_changed')
                before[path]=result
            old_ip=json.loads(run(['docker','inspect',old]))[0]['NetworkSettings']['Networks'][network]['IPAddress']
            run(['docker','network','disconnect',network,old])
            server('old-ip-occupant','WRONG_ROLE',address=old_ip)
            new=server('new-backend','B',alias='backend')
            new_ip=json.loads(run(['docker','inspect',new]))[0]['NetworkSettings']['Networks'][network]['IPAddress']
            if new_ip==old_ip:raise RuntimeError('frontend_dns_fixture_ip_did_not_change')
            started=time.monotonic();after={}
            for path,expected in paths.items():
                result=await_role('B',path)
                if result['path']!=expected:raise RuntimeError('frontend_dns_fixture_uri_changed')
                after[path]=result
            return {'operation':'actual-isolated-frontend-role-reassignment','nginx_image':NGINX,
                    'template_sha256':hashlib.sha256(template).hexdigest(),'old_backend_ip':old_ip,'new_backend_ip':new_ip,
                    'old_address_occupied_by_wrong_role':True,'before':before,'after':after,
                    'convergence_seconds':round(time.monotonic()-started,3),'production_modified':False}
        finally:
            for name in reversed(owned):run(['docker','rm','--force',name])
            run(['docker','network','rm',network])

if __name__=='__main__':
    import sys
    template=Path(sys.argv[1]).read_bytes()
    try:print(json.dumps(test(template)))
    except Exception as error:print(json.dumps({'operation':'actual-isolated-frontend-role-reassignment','status':'failed','exception_type':type(error).__name__,'stage':str(error) if type(error) is RuntimeError else 'fixture_failed'}));sys.exit(1)
