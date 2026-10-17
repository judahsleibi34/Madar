#!/usr/bin/env python3
"""INSPECT loopback worker health/metrics; emit bounded alerts, never send messages."""
import argparse
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler

PREFIX='madar_notification_worker_'
NAMES=('processed','sent','failed','dead','ownership_lost','acknowledgement_failed','queue_depth','oldest_pending_age_seconds')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def inspect(base,instance,expected_consuming,previous=None):
    parsed=urlsplit(base)
    if (parsed.scheme!='http' or parsed.hostname not in {'127.0.0.1','::1'} or parsed.port is None
            or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment
            or not re.fullmatch('[0-9a-f]{64}',instance)):
        raise RuntimeError('Explicit loopback worker and immutable container identity required')
    opener=build_opener(ProxyHandler({}),NoRedirect())
    def get(path):
        try:response=opener.open(Request(base.rstrip('/')+path),timeout=3)
        except HTTPError as error:response=error
        with response:
            data=response.read(65537)
            if len(data)>65536:raise RuntimeError('Worker response exceeds inspection bound')
            return response.status,data
    status,body=get('/health');health=json.loads(body)
    metric_status,body=get('/metrics');metrics={}
    if metric_status!=200:raise RuntimeError('Worker metrics unavailable')
    for line in body.decode().splitlines():
        fields=line.split()
        if len(fields)==2 and fields[0] in {PREFIX+name for name in NAMES}:
            name=fields[0][len(PREFIX):]
            if name in metrics or not re.fullmatch('[0-9]+',fields[1]):raise RuntimeError('Worker metric invalid')
            metrics[name]=int(fields[1])
    if set(metrics)!=set(NAMES) or type(health.get('consuming')) is not bool:
        raise RuntimeError('Worker inspection incomplete')
    prior={name:0 for name in NAMES};reset=False
    if previous is not None:
        if (previous.get('mode')!='INSPECT' or previous.get('instance_id')!=instance
                or not isinstance(previous.get('metrics'),dict) or set(previous['metrics'])!=set(NAMES)
                or any(type(value) is not int or value<0 for value in previous['metrics'].values())):
            raise RuntimeError('Different or invalid previous worker snapshot')
        prior=previous['metrics'];reset=any(metrics[name]<prior[name] for name in NAMES[:6])
        if reset:prior={name:0 for name in NAMES}
    alerts=[]
    if status!=200 or health.get('status')!='ok':alerts.append('WORKER_UNHEALTHY')
    if health['consuming']!=expected_consuming:alerts.append('CONSUMPTION_AUTHORITY_MISMATCH')
    if metrics['ownership_lost']>prior['ownership_lost']:alerts.append('DELIVERY_OWNERSHIP_LOST')
    if metrics['acknowledgement_failed']>prior['acknowledgement_failed']:alerts.append('DELIVERY_ACKNOWLEDGEMENT_FAILED')
    if metrics['queue_depth'] and metrics['oldest_pending_age_seconds']>=300:alerts.append('NOTIFICATION_BACKLOG_AGE')
    return {'mode':'INSPECT','instance_id':instance,'status':'FAIL' if alerts else 'PARTIAL' if reset else 'PASS',
        'metrics':metrics,'alerts':alerts,'counter_reset_observed':reset,'consuming':health['consuming'],
        'actions_performed':False,'limitations':['process counters reset on restart','queue gauges use bounded outbox/delivery snapshots',
            'inspection is not consumption authority or provider reconciliation']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--base-url',required=True)
    parser.add_argument('--instance-id',required=True);parser.add_argument('--expected-consuming',choices=('yes','no'),required=True)
    parser.add_argument('--previous',type=Path);args=parser.parse_args()
    previous=None
    if args.previous:
        if args.previous.is_symlink() or args.previous.stat().st_size>65536:raise RuntimeError('Previous snapshot scope invalid')
        previous=json.loads(args.previous.read_text())
    print(json.dumps(inspect(args.base_url,args.instance_id,args.expected_consuming=='yes',previous),sort_keys=True))
