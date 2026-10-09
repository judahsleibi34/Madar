"""Current-data fallback verification under a fresh continuation authority.

Does not reconstruct old credentials, alter receipts or restore a database.
This verifier is a component, not a production bootstrap or complete cutover.
It resolves measured destinations per invocation and rejects active consumers.
Historical controller identity may have been superseded only by the fresh
continuation; unchanged native/fallback identities remain mandatory.
"""
from dataclasses import asdict
import json
import ipaddress
import os
from pathlib import Path

from deployment.lib.active_recovery_resumption import ROOT
from deployment.lib.active_recovery_inputs import INPUTS,PRIVATE_CONFIGURATION
from deployment.lib.provider_recovery_runtime import SERVICES,protected,readonly_configuration,digest,file_digest
from deployment.lib.emergency_routing_repair import Runtime,spec,require

UNCHANGED=frozenset({'recovery_transaction','local_transaction','recovery_contract','schema_contract',
    'local_contract','write_authority','fallback','local_configuration','native_configuration',
    'native_compose','native_override','gateway_bootstrap','gateway_cds','gateway_lds'})
KINDS=('notification','calendar-sync','data-deletion')

class CurrentDataFallback:
    def __init__(self,plan,root,*,runtime=None):
        plan.validate();self.plan=plan;self.root=Path(root);self.runtime=runtime or Runtime()

    def require_compensation_authority(self):
        require(os.geteuid()==0 and self.root==ROOT/self.plan.digest,'fallback_fresh_root_required')
        receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        require(receipt.get('operation')=='active-local-rollback-resumption' and
            receipt.get('plan_sha256')==self.plan.digest and receipt.get('source_bundle_sha256')==self.plan.source_bundle_sha256,
            'fallback_fresh_authorization_changed')
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        require(events and all(e.get('plan_sha256')==self.plan.digest for e in events) and
            events[-1].get('phase') in {'compensation_pending','restricted_fallback'},'fallback_compensation_not_authorized')
        # Positive normal authority must already be revoked before forwarding.
        authority=json.loads(protected(self.root/'write-authority/authority.json').read_text())
        candidate=json.loads(protected(self.root/'candidate-identities.json',private=True).read_text())
        require(authority.get('mode')=='READ_ONLY' and authority.get('schema')==115 and
            authority.get('release_sha')==self.plan.source_sha and candidate.get('plan_sha256')==self.plan.digest and
            candidate.get('source_sha')==self.plan.source_sha,'fallback_normal_authority_not_fenced')

    def verify_registered_runtime(self):
        # Observation only: does not authorize forwarding, publication or writes.
        for key in UNCHANGED:
            reader=readonly_configuration if key in {'recovery_transaction','fallback','native_configuration','native_compose','native_override','gateway_bootstrap','gateway_cds','gateway_lds'} else protected
            require(file_digest(reader(INPUTS[key],private=key in PRIVATE_CONFIGURATION))==self.plan.retained_inputs[key],
                'fallback_retained_input_changed')
        for key in ('recovery_transaction','local_transaction'):
            require(json.loads(INPUTS[key].read_text()).get('phase')=='local_rollback_active','fallback_transaction_changed')
        dependencies=json.loads(protected(self.root/'runtime-dependencies.json',private=True).read_text())
        require(digest(dependencies)==self.plan.retained_inputs['runtime_dependencies'],'fallback_dependency_record_changed')
        native=self.runtime.inspect(list(SERVICES))
        for name in SERVICES:
            row=native[name];expected=dependencies['runtimes'][name]
            require({'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row),
                'running':row['State']['Running'],'networks':{k:v['NetworkID'] for k,v in row['NetworkSettings']['Networks'].items()}}==expected,
                'fallback_native_identity_changed')
            require(row['State']['Running'] and row['State'].get('Health',{}).get('Status')=='healthy','fallback_native_unhealthy')
        rows=self.runtime.inspect([entry['container_id'] for entry in self.plan.fallback.values()]);by_id={row['Id']:row for row in rows.values()}
        endpoints={};initial={}
        for role,expected in self.plan.fallback.items():
            row=by_id[expected['container_id']];initial[role]=row
            require(row['Image']==expected['image_id'] and spec(row)==expected['spec_sha256'] and row['State']['Running'],
                'fallback_registered_identity_changed')
            require(not any(row['NetworkSettings']['Ports'].values()),'fallback_public_binding_changed')
            networks=row['NetworkSettings']['Networks']
            matches=[(name,value) for name,value in networks.items() if role in (value.get('Aliases') or [])]
            require(len(matches)==1,'fallback_runtime_role_invalid')
            network_name,attachment=matches[0]
            network=self.runtime.network(network_name)
            require(network['Id']==attachment['NetworkID'] and network['Internal'] is True and network['Driver']=='bridge',
                'fallback_runtime_network_invalid')
            address=ipaddress.ip_address(attachment['IPAddress'])
            require(address.version==4 and address.is_private,'fallback_destination_not_private')
            endpoints[role]=(str(address),8000 if role=='backend' else 8080)
        require(endpoints['backend'][0]!=endpoints['frontend'][0],'fallback_role_collision')
        self.runtime.schema()
        backend='http://%s:%d'%endpoints['backend']
        ready=self.runtime.json_http(backend+'/health/ready');version=self.runtime.json_http(backend+'/health/version')
        require(ready.get('ready') is True and all(ready.get('components',{}).get(k)=='ok' for k in ('database','auth','schema','storage')),
            'fallback_readiness_failed')
        source=initial['backend']['Config'].get('Labels',{}).get('org.opencontainers.image.revision')
        require(version.get('release_sha')==source and version.get('release_slot')=='local-fallback' and
            version.get('schema_compatible_min')==version.get('schema_compatible_max')==115,'fallback_version_invalid')
        require(self.runtime.json_http(backend+'/health/recovery')=={'restricted':True,'business_writes_enabled':False},'fallback_business_fence_failed')
        self.runtime.denied(backend);self.runtime.http_status('http://%s:%d/'%endpoints['frontend'])
        latest=self.runtime.inspect([row['Id'] for row in initial.values()]);latest={row['Id']:row for row in latest.values()}
        for role,row in initial.items():
            current=latest[row['Id']]
            require(spec(current)==spec(row) and current['State']['Running'] and
                current['NetworkSettings']['Networks']==row['NetworkSettings']['Networks'],'fallback_changed_during_verification')
        return endpoints

    def verify(self):
        self.require_compensation_authority()
        dependencies=json.loads(protected(self.root/'runtime-dependencies.json',private=True).read_text())
        require(digest(dependencies)==self.plan.retained_inputs['runtime_dependencies'],'fallback_dependency_record_changed')
        names=self.runtime.names()
        consumers=[name for name in names if name.startswith('madar-') and
            any(kind+'-worker' in name or name.endswith(kind+'-standby') for kind in KINDS)]
        expected_consumers={f'madar-{slot}-{kind}-worker' for slot in ('blue','green') for kind in KINDS}
        # Canonical names may be archived only by governed ownership handoff;
        # retained IDs must still exist and be stopped, in addition to all names.
        old_ids=[dependencies['runtimes'][name]['container_id'] for name in expected_consumers]
        for row in self.runtime.inspect([*consumers,*old_ids]).values():
            require(row['State']['Running'] is False and row['HostConfig']['RestartPolicy']['Name']=='no','fallback_consumer_not_stopped')
        endpoints=self.verify_registered_runtime()
        self.require_compensation_authority()
        return endpoints


# New scoped listeners leave the functioning emergency helper/ports untouched.
# Existing reviewed frontend API interception is preserved on these listeners.
from deployment.lib.emergency_routing_repair import ROUTE,Relay,DENIED,MAINTENANCE,AvailabilityFailure,verification_window
import select
import socket
import socketserver
import time

FALLBACK_PORTS={'backend':29501,'frontend':39501}
FALLBACK_ROUTE=ROUTE.replace(b'29401',b'29501').replace(b'39401',b'39501').replace(b'39402',b'39502')

class RestrictedForward(socketserver.BaseRequestHandler):
    def handle(self):
        remote=None
        try:
            # Mandatory frozen-source guard is supplied by the complete trusted
            # bootstrap; there is no default bypass or old approval reuse.
            self.server.source_guard()
            # A separate monotonic budget/runtime per connection prevents one
            # listener thread from extending or clearing another's deadline.
            measured=Runtime();measured.deadline=time.monotonic()+30
            verifier=CurrentDataFallback(self.server.verifier.plan,self.server.verifier.root,runtime=measured)
            endpoints=verifier.verify();measured.budget(1)
            remote=socket.create_connection(endpoints[self.server.role],timeout=8)
            remote.settimeout(30);self.request.settimeout(30)
            while True:
                readable,_,_=select.select([self.request,remote],[],[],300)
                if not readable:return
                for incoming in readable:
                    data=incoming.recv(65536)
                    if not data:return
                    (remote if incoming is self.request else self.request).sendall(data)
        except Exception as error:
            print(json.dumps({'event':'normal_continuation_fallback_connection_denied',
                'exception_type':type(error).__name__}),flush=True)
            try:self.request.sendall(DENIED)
            except OSError:pass
        finally:
            if remote is not None:remote.close()


def restricted_listeners(verifier,source_guard):
    """Construct NEW listeners only; caller manages audited service lifecycle."""
    require(callable(source_guard),'fallback_frozen_source_guard_required')
    source_guard();servers=[]
    try:
        for role,port in FALLBACK_PORTS.items():
            server=Relay(('127.0.0.1',port),RestrictedForward)
            servers.append(server);server.verifier=verifier;server.role=role;server.source_guard=source_guard
        return servers
    except Exception:
        for server in servers:server.server_close()
        raise

class CompensationPublication:
    """Bounded publication AFTER write fencing and consumer shutdown.

    A separately approved bootstrap must have installed the NEW fail-closed
    listeners. Publication never rewrites the original helper or its records.
    Callback checks must measure both public routes, source and restrictions.
    """
    def __init__(self,verifier,root,*,runtime=None):
        self.verifier=verifier;self.root=Path(root);self.runtime=runtime or Runtime()
        self.runtime.expected_nginx_sha256=verifier.plan.retained_inputs['proxy_configuration']

    def publish(self,verify_public_round):
        with verification_window(self.runtime,60):
            self.verifier.verify()
            self.runtime.nginx_preflight(FALLBACK_ROUTE,self.root)
            self.runtime.publish(FALLBACK_ROUTE);self.runtime.reload()
            first=None;consecutive=0
            while True:
                self.runtime.budget(1)
                try:
                    self.verifier.verify();verify_public_round(FALLBACK_ROUTE)
                except AvailabilityFailure:
                    first=None;consecutive=0
                else:
                    consecutive+=1
                    if first is None:first=time.monotonic()
                    if consecutive>=3 and time.monotonic()-first>=5:return
                time.sleep(self.runtime.budget(1))

    def maintenance_or_stop_proxy(self):
        try:
            with verification_window(self.runtime,60):
                # Fail-closed publication does not require the unavailable
                # fallback to pass. Never attempt a database or volume restore.
                self.runtime.nginx_preflight(MAINTENANCE,self.root)
                self.runtime.publish(MAINTENANCE);self.runtime.reload()
                self.runtime.verify_maintenance()
        except Exception:
            self.runtime.stop_proxy()
